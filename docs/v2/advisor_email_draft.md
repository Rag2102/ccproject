# Advisor email (draft; v2 Appendix A.1, adjusted for the v5 plan)

Not sent. Fill the three placeholders, add the advisor's name, and send by Friday 9 Oct 2026. The plan wants the charter, the v1 anomaly note and protocol v0 to follow in Weeks 2-3; ask for the meeting first.

Subject: Request for guidance: extending my Cloud Computing project into a paper

Dear Professor <name>,

I am a student in <your course/program>. My Cloud Computing project studies workload-aware, cost-sensitive mitigation of predicted VM failures, compared with a probability-threshold baseline (framed against Microsoft's Narya, OSDI 2020). It uses public data (Azure VM trace, Backblaze drive stats) and a replay simulator.

The result so far is conditional: at a matched migration budget the cost-sensitive policy was 3.1% behind the threshold when placement was random, and ahead by up to 3.4% once I made workload criticality correlate with host risk, which I set synthetically. I plan to measure that correlation in real placement traces, derive when the advantage appears, and write it up for a conference, with an open benchmark of the policies.

Would you be willing to advise, or suggest someone who could? I can send a two-page summary and the repository before we meet. In particular I would value your view on what you would attack first.

Thank you,
<name>

---
Facts behind each sentence: -3.1% and +3.4% are in `docs/v2/v1_final_state.md`; the repository is `github.com/Rag2102/ccproject` (private until you decide otherwise: check before sharing a link); the plan's wording says 26 weeks, v5 extends it to 60.
