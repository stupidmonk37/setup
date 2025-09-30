# list of things to do, in no particular order of priority or importance (yet):

# thoughts:
- Instead of having faults AND the cluster table displayed at the same time,
  should there be a "Cluster" and "Faults & Tickets" tab? ✅
  - Separate tabs
- Role of app - Push & pull (fw update, stop/retry/requalify, restart tspd), or only pull? ✅
  - Pull only ATM

# high level & not technical:
- Create separate repo for all things dc-validation-status
- Naming - do we keep dc-validation-status or come up with something sweet?
- Dedicated Slack channel

# technical:
- Improve homepage performance (cluster table loads slowly)
- Add "BMC Match" column to the cluster table ✅
- Make "Rack Validation" and "Crossrack Validation" columns clicky ✅
- Change order of "Validation Status" and "Pre-Validation" tabs ✅
- Expose validator logs in the rackmodal
- Add tickets and faults to summary blocks ✅
- Add url for Jira Epic somewhere
- Fallback to "validation.groq.io" labels for validation status
- Auto pop up web page ✅
- PDU performance
- PDU mapping
- Show taints ✅
- crosspod cable lengths - image of floorplan?
- Test failure / success rates
