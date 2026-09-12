# Quality assurance — image-creator: icon

Read [common quality assurance](../../SKILL.md) first.

For an icon, the size-of-use look (common quality assurance's numbered step
2) is a 64 px sidebar/Slack icon or a 16 px favicon — resize the recommended
variant to whichever destination the client named, not just the delivered
1024 px canvas. Read the hands' `RESULT:` line (dimensions, background
coverage, corner alpha) and cut-out/subject/style verdicts against the
`what_for`/`style`/`background`/`palette` the client actually asked for; a
variant marked failing in the report is still weighed against intent, never
silently ignored. `generate-icon` does not produce an SVG — a dependent
`create-icon` request on this delivery's file needs its own separately
released form, never a local vector trace of the PNG. No new measurement is
taken here: the finish script's coverage/alpha numbers and the hands' style
cues are the evidence, not a fresh crop or resize beyond the size-of-use
scratch copy.

The verdict and delivery-to-client shape are common — see
[common quality assurance](../../SKILL.md).
