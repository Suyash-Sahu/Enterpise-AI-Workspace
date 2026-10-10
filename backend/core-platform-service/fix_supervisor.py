import sys

old = (
    "                    last_step = plan.steps[-1] if plan.steps else None\n"
    "                    if not last_step:\n"
    "                        break\n"
    "\n"
    "                    cdrp_tried_capabilities.add(last_step.capability)\n"
    "                    replan_step, replan_event = cdrp_replanner.replan(\n"
    "                        db=db,\n"
    "                        context=context,\n"
    "                        plan=plan,\n"
    "                        failed_step=last_step,\n"
    "                        report=report,\n"
    "                        replan_count=replan_count,\n"
    "                        tried_capabilities=cdrp_tried_capabilities,\n"
    "                    )"
)

new = (
    "                    # Phase 30: use FailureAttributor instead of the blunt\n"
    "                    # steps[-1] proxy (Phase 4 documented limitation).\n"
    "                    step_reports_inner: dict[str, Optional[str]] = {\n"
    "                        sid: (wf.verification_json if wf is not None else None)\n"
    "                        for sid, wf in wf_step_rows.items()\n"
    "                    }\n"
    "                    attribution = failure_attributor.attribute(\n"
    "                        plan=plan,\n"
    "                        step_reports=step_reports_inner,\n"
    "                        final_report=report.to_dict(),\n"
    "                    )\n"
    "                    plan_map_inner = {s.step_id: s for s in plan.steps}\n"
    "                    attributed_step = plan_map_inner.get(attribution.suspect_step_id)\n"
    "                    # Fall back to last step only for synthesis attribution or unknown\n"
    "                    if attributed_step is None or attribution.suspect_step_id in (\n"
    '                        "step_synthesis", "unknown"\n'
    "                    ):\n"
    "                        attributed_step = plan.steps[-1] if plan.steps else None\n"
    "                    last_step = attributed_step\n"
    "                    if not last_step:\n"
    "                        break\n"
    "\n"
    "                    cdrp_tried_capabilities.add(last_step.capability)\n"
    "                    replan_step, replan_event = cdrp_replanner.replan(\n"
    "                        db=db,\n"
    "                        context=context,\n"
    "                        plan=plan,\n"
    "                        failed_step=last_step,\n"
    "                        report=report,\n"
    "                        replan_count=replan_count,\n"
    "                        tried_capabilities=cdrp_tried_capabilities,\n"
    "                    )"
)

path = "app/supervisor/supervisor.py"
content = open(path, "r", encoding="utf-8").read()
content_unix = content.replace("\r\n", "\n")

if old in content_unix:
    content_new = content_unix.replace(old, new, 1)
    content_new = content_new.replace("\n", "\r\n")
    open(path, "w", encoding="utf-8").write(content_new)
    print("REPLACED OK")
else:
    print("NOT FOUND")
    idx = content_unix.find("last_step = plan.steps[-1] if plan.steps else None")
    print(f"Index: {idx}")
    print(repr(content_unix[max(0, idx-50):idx+300]))
    sys.exit(1)
