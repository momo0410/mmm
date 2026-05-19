def run(
    target: str,
    llm_fn: Callable[..., str],
    state_path: str = "state.json",
    max_rounds: int = 30,
    dry_run: bool = False,
    parallel_execution: bool = False,
    auto_phase: bool = True,
    skill_query: Optional[str] = None,
    skill_limit: int = 3,
) -> str:
    from app.services.skill_engine import SkillLoader
    from app.services.skill_engine.skill_matcher import SkillMatcher

    state = State(state_path)

    for t in re.split(r"[,; ]+", str(target).strip()):
        t = t.strip()
        if t:
            state.add_target(t)

    loader = SkillLoader(SKILLS_ROOT)
    matcher = SkillMatcher(loader)

    executor = Executor(state=state)
    shell_lock = threading.Lock()

    doctor_report = executor.doctor()
    summary = doctor_report.get("summary", {})
    ok_c = summary.get('ok', 0)
    warn_c = summary.get('warn', 0)
    err_c = summary.get('error', 0)

    _log("INFO", "DOCTOR", f"ok={ok_c} warn={warn_c} error={err_c} total={summary.get('total',0)}")

    if err_c:
        for t in doctor_report.get("tools", []):
            if t.get("status") == "error":
                _log("WARN", "DOCTOR", f"tool={t['tool']} issues={'; '.join(t.get('issues',[]))}")

    _log_doctor_report(state, doctor_report)

    consecutive_llm_failures = 0

    consecutive_skip_rounds = 0

    llm_stream_enabled = _llm_fn_supports_stream_callback(llm_fn)
    _log("INFO", "LLM", f"stream_callback_supported={llm_stream_enabled}")

    try:
        for round_num in range(1, max_rounds + 1):
            round_start = _time.monotonic()
            phase = state.data['phase']
            _log("INFO", "ROUND", f"========== Round {round_num}/{max_rounds} phase={phase} ==========")

            tools_desc = executor.list_tools()
            system = SYSTEM_PROMPT.format(tools_list=tools_desc)
            skill_query_text = _build_skill_query_text(state, target, skill_query)
            skill_matches = matcher.match(skill_query_text, limit=skill_limit)
            skill_knowledge = matcher.format_knowledge_for_prompt(skill_matches)
            if skill_matches:
                _log("INFO", "SKILLS", f"query=\"{skill_query_text[:160]}\"", match_count=len(skill_matches))
                for m in skill_matches:
                    _log("DEBUG", "SKILLS", f"  {m.skill.name} score={m.score:.1f} has_md={m.skill.md_data is not None}")
            if skill_knowledge:
                system = system + "\n\n" + skill_knowledge
            user = state.llm_context()

            finish_llm_wait, on_llm_chunk = _start_llm_planning_progress(state, round_num)
            llm_start = _time.monotonic()
            try:
                if llm_stream_enabled:
                    response = llm_fn(system, user, on_llm_chunk)
                else:
                    response = llm_fn(system, user)
                consecutive_llm_failures = 0
            except Exception as exc:
                consecutive_llm_failures += 1
                llm_dur = _time.monotonic() - llm_start
                backoff_s = min(30, max(2, 3 * consecutive_llm_failures))
                err_text = str(exc)
                finish_llm_wait(
                    False,
                    detail=f"LLM 请求失败，{backoff_s}s 后重试",
                    error=err_text,
                )
                _log(
                    "ERROR",
                    "LLM",
                    f"round={round_num} llm request failed after {llm_dur:.1f}s; "
                    f"consecutive_failures={consecutive_llm_failures}; backoff={backoff_s}s; err={err_text[:260]}"
                )
                state.log_action(
                    "_llm_error",
                    f"round={round_num}",
                    result_summary=f"LLM request failed: {err_text[:400]}",
                    full_stdout=err_text,
                    llm_decision="LLM 调用超时/网络异常，本轮跳过并自动重试。",
                    error=err_text[:1200],
                )
                state.log_action(
                    "_token_usage",
                    f"round={round_num}",
                    result_summary="LLM request failed before usage metadata was returned.",
                    full_stdout=err_text[:1200],
                    llm_decision="本轮未记录 token 消耗：LLM 请求失败，未收到 usage 元数据。",
                    error=err_text[:400],
                )

                if consecutive_llm_failures >= MAX_CONSECUTIVE_LLM_FAILURES:
                    reason = (
                        f"连续 {consecutive_llm_failures} 轮 LLM 调用失败，"
                        "为避免无限重试，任务提前结束。"
                    )
                    _log("ERROR", "AGENT", reason)
                    state.log_action(
                        "_done",
                        "",
                        result_summary=reason,
                        llm_decision=reason,
                        error=reason,
                    )
                    state.set_phase("done")
                    break

                _time.sleep(backoff_s)
                continue
            llm_dur = _time.monotonic() - llm_start
            finish_llm_wait(True, detail=f"LLM 规划完成，用时 {llm_dur:.1f}s")
            client = get_llm_client()
            usage_recorded = False
            if client and client.last_usage:
                usage_recorded = state.record_token_usage(
                    "pentest_llm",
                    client.last_usage,
                    model=getattr(client, "model", ""),
                    provider=getattr(client, "provider", ""),
                )
                if usage_recorded:
                    state.log_action(
                        "_token_usage",
                        f"round={round_num}",
                        result_summary=(
                            f"category=pentest_llm prompt={int(client.last_usage.get('prompt_tokens', 0) or 0)} "
                            f"completion={int(client.last_usage.get('completion_tokens', 0) or 0)} "
                            f"total={int(client.last_usage.get('total_tokens', 0) or 0)}"
                        ),
                        llm_decision="已记录本轮主流程 LLM token 消耗。",
                    )
            if not usage_recorded:
                provider_name = getattr(client, "provider", "") if client else ""
                model_name = getattr(client, "model", "") if client else ""
                missing_reason = "LLM provider did not return usage metadata."
                if not client:
                    missing_reason = "LLM client unavailable; usage metadata could not be collected."
                state.log_action(
                    "_token_usage",
                    f"round={round_num}",
                    result_summary=missing_reason,
                    llm_decision=(
                        "本轮未记录 token 消耗：上游响应未返回 usage 元数据。"
                        if client else
                        "本轮未记录 token 消耗：当前未获取到 LLM 客户端上下文。"
                    ),
                    full_stdout=f"provider={provider_name} model={model_name}".strip(),
                )
            llm_thinking = _extract_any_tag(response, ["think", "thinking", "thought"])
            if not llm_thinking:
                llm_thinking = response.strip()
            _log("INFO", "LLM", f"duration={llm_dur:.1f}s response_len={len(response)} first_line=\"{response.split(chr(10))[0][:200]}\"")
            _log("DEBUG", "LLM", f"raw_response={response[:800]}")

            _check_llm_response_quality(response)

            if "<done>" in response:
                reason = _extract_tag(response, "done")
                blocked_reason = _should_block_done(state)
                if blocked_reason:
                    _log("WARN", "AGENT", f"done blocked: {blocked_reason}")
                    state.log_action(
                        "_done_blocked",
                        "",
                        result_summary=blocked_reason,
                        llm_decision=llm_thinking or reason,
                    )
                    continue
                _log("INFO", "AGENT", f"done reason=\"{reason}\"")
                state.log_action("_done", "", "", llm_decision=llm_thinking or reason)
                state.set_phase("done")
                break

            plan = _extract_plan(response)
            tasks = _normalize_plan_tasks(plan)
            if not tasks:
                legacy_task = _extract_legacy_task(response)
                if legacy_task:
                    tasks = [legacy_task]
                    _log("DEBUG", "PARSE", "使用旧格式 <tool>/<args> 降级解析")

            if not tasks:
                tasks = _deterministic_parse_fallback_tasks(state, llm_thinking or response)
                if tasks:
                    _log("WARN", "PARSE", "LLM 输出无法解析有效任务，回退到 deterministic fallback")

            if not tasks:
                tasks = _fallback_to_candidate_tasks(state)
                if tasks:
                    _log("WARN", "PARSE", "LLM 输出无法解析有效任务，回退到 planner 候选任务")

            tasks = _apply_phase_task_defaults(tasks, state)
            tasks = _enrich_task_identity(tasks, state)
            tasks = _enforce_minimal_task_policy(tasks, state)

            if not tasks:
                consecutive_skip_rounds += 1
                _log("WARN", "PARSE",
                     f"LLM 输出中未找到有效工具调用, 跳过本轮 (连续跳过={consecutive_skip_rounds})")
                state.log_action("_skip", response[:200], "no tool tag found",
                                 llm_decision=llm_thinking)
                if consecutive_skip_rounds >= MAX_CONSECUTIVE_SKIP_ROUNDS:
                    reason = (f"连续 {consecutive_skip_rounds} 轮 LLM 输出无法解析为有效任务，"
                              "为避免空转终止任务")
                    _log("ERROR", "AGENT", reason)
                    state.log_action("_done", "", result_summary=reason, llm_decision=reason)
                    state.set_phase("done")
                    break
                continue

            consecutive_skip_rounds = 0

            state.record_round_plan(
                round_num=round_num,
                round_goal=str((plan or {}).get("round_goal", "")) if isinstance(plan, dict) else "",
                continue_reason=str((plan or {}).get("continue_reason", "")) if isinstance(plan, dict) else "",
                tasks=tasks,
            )

            _log("INFO", "PLAN", f"本轮 {len(tasks)} 个任务 goal=\"{str((plan or {}).get('round_goal',''))[:120]}\"")
            for task in tasks:
                tool = task['tool']
                args = task['args']
                surf = task['surface']
                ports = task.get('ports',[])
                ports_str = f" ports={ports}" if ports else ""
                _log("INFO", "TASK", f"[{task['task_label']}] {surf} -> {tool} {args}{ports_str}")

            before_counts = state.evidence_counters()
            _execute_planned_tasks(
                tasks=tasks,
                executor=executor,
                state=state,
                llm_thinking=llm_thinking,
                round_num=round_num,
                dry_run=dry_run,
                shell_lock=shell_lock,
                parallel_execution=parallel_execution,
            )
            state.finalize_round(round_num, before_counts, state.evidence_counters())

            if auto_phase:
                old_phase = state.data["phase"]
                _auto_phase_switch(state)
                new_phase = state.data["phase"]
                if new_phase != old_phase:
                    _log("INFO", "PHASE", f"{old_phase} -> {new_phase}")
                if new_phase == "done":
                    break

            round_dur = _time.monotonic() - round_start
            _log("INFO", "ROUND", f"round={round_num} duration={round_dur:.1f}s phase={state.data['phase']}")
    finally:
        executor.close_all_sessions()

    report_path = state.generate_report()
    _log("INFO", "AGENT", f"report={report_path}")
    return report_path