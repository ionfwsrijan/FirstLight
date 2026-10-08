# FirstLight — 3-minute demo film playbook

Rule of the competition: a 3-minute **pre-recorded** video, no live demo. The
film must look deterministic even though it is recorded. So the film IS the
deterministic demo, run for real, on camera. This is not a mock.

## Structure (goal: 3:00 ± 10s)

| Time | Beat | What is on screen | Why it lands |
|---|---|---|---|
| 00:00 | Cold open | Phone face-down, 05:57 shows, alarm, "6 AM" | The exact moment. No intro slide yet. |
| 00:15 | The question | a parent asks the console, out loud, on camera: *"good morning — is today safe for school?"* | The 3-word job. |
| 00:22 | It answers | FirstLight replies: RED, AQI, GRAP, fires | The whole product in 7 seconds. |
| 00:30 | Why | Ask "why?" — it cites the band table line | The AI narrates, the engine decides. |
| 00:42 | What do we do | Action list for a RED day | It turns the decision into a to-do. |
| 00:55 | Send it | Say "send it" — certificate with reference number appears | Consent-from-transcript, in front of the camera. |
| 01:08 | The objection | Camera-zoom: *"Yes" should do nothing.* Say "yes", show nothing happens. Then say "cancel the alert" → recall. | This is the safety-model bit. It wins trust in 10 seconds. |
| 01:28 | The engine | Split screen: `/tests` green, then the single-line rule table in `bands.py` | "One feature that runs" + open-source honesty. |
| 01:45 | Replay proof | Press "Run the bad morning" again → byte-identical transcript | Deterministic, film-proof, zero AWS flake. |
| 02:05 | Build It | `py -m unittest discover -s tests`: 60/60 green. No card, no verified account. | The credential objection, pre-empted. |
| 02:20 | The gap | Closing: same decision at 6 AM, city-wide, before symptoms show. | Impact, not features. |
| 02:40 | Hook | "A child's school day should not depend on who checked the news first." + repo line. | The one line they quote. |

## Capture checklist

- Single take, no cuts, phone screen + mic. The demo is short enough to run once.
- Record at 1280x720 or higher. Overlay English subtitles (caller text is on-screen).
- Never let the video outrun the code: every reply you show was produced during
  this recording run, or it is a frozen-frame of the same deterministic text.
- If anything on screen diverges, restart the take. There are no live APIs to fail.

## The trailer (if uploading a short)

> "Every Delhi winter, the school call comes too late. FirstLight is the 6 AM call
> that comes first: the AQI table, the GRAP plan, and the stubble fires, decided
> by rules beneath the narration — and it will not send a word without consent."

## Repository links to drop into the description

- Build It, no AWS account needed (runs in 10 seconds, stdlib only).
- Ship It shape documented; demo makes zero network calls, so it cannot flake.