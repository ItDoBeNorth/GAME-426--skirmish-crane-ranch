# Skirmish at Crane Reach agent

Edit `agent.py` to build one unit's behavior for Skirmish at Crane Reach. Every unit on a side runs a separate instance of the same `Agent` class, so they do not share state or variables. `sandbox/` is provided code: do not edit it.

Start with the [Getting Started guide](https://vox-deorum.github.io/game-sandbox/students/getting-started/). Then run these commands from this folder as you work:

```console
python -m sandbox play   # command a side yourself in your browser
python -m sandbox watch  # watch your agent take on Naive
python -m sandbox test   # run the provided checks
python -m sandbox eval   # compare your agent with Naive
```

**Naive** is a simple built-in opponent. It holds the other side in `watch` and `eval`, and `eval` reports your side's average score over repeatable matches. The [`environment.md`](environment.md) guide explains rivals, presets, and the other command options.

## Files you will use

| Path | Purpose |
| --- | --- |
| `agent.py` | Your `Agent` implementation and the first TODO locations. |
| `environment.md` | Crane rules, starter walkthrough, helpers, observations, and settings. |
| `manifest.json` | Names the agent class for a submission. |
| `season.json` | Optional local season settings downloaded from My Submissions. |
| `tests/` | Checks your submission should pass. |
| `sandbox/` | Local game, commands, helper package, and observation types. Do not edit it. |
| `requirements.txt` | Exact Python package versions used by the server. |
| `requirements-dev.txt` | Test dependencies. |
| `.env.example` | Example local LLM settings. |

The starter returns Crane orders with `action.move()` and `action.stay()` from `sandbox.crane`. Its `act(observation)` receives the current observation and action mask. Before changing the strategy, read [`environment.md`](environment.md). It starts with a small archer improvement you can copy, then explains when an order is legal.

Leave `sandbox/`, `requirements.in`, and `requirements.txt` unchanged. The pinned packages match the server. Ask your instructor before adding a package.

When your agent is ready, follow the shared [submitting guide](https://vox-deorum.github.io/game-sandbox/students/submitting/). For the optional `learn` and `chat` hooks, see the shared [agent interface](https://vox-deorum.github.io/game-sandbox/students/agent-interface/). Crane messaging begins in Season 3.

## Design Goal
Season 1: The goal this season was to have the units move intentionally, look for and keep track of each other and the enemies by moving to the center, and target enemies in the most efficient way with attack priority, fallback, and rescue. The archers should look for enemies and the other archer; the cavalry should look for its allies and attack all non-archers quickly; the footmen should do the same while fleeing from the enemy archer. 

## Reflection
Season 1: I considered techniques of behavior based on role and health, keeping track of where allies and enemies were last seen, tracking enemy threat distance, prioritizing attacking certain roles, checking the cost of attacking vs. fleeing, supporting allies through rescue, and the archer covering allies and removing the enemy archer early. The hardest part was calculating the threat and whether taking the chance of attacking rather than fleeing was worth it- it took a lot of tries and wasn't possible to check for more than one turn since the units couldn't communicate. One part that helped was the units having a bias to the center and keeping track of last-seen allies and enemies, as it allowed units to support and protect each other and prioritize high-potential threat enemies. The logic for it got complicated quite quickly but raised the mean score significantly. I think I would rework these two and look into how I can protect the archer from the cavalry better, as that was why many games were lost. Something I struggled with and had to revert was whether cavalry/footmen would risk getting help to support another ally, and calculating the cavalry's risk assessment past two turns from the archer. I might try adding memory caps and risk assessments next time.


## AI Use Disclosure and Reflection
I used Claude to refine my ideas and pseudocode and discussed possible issues and solutions with it before having it format information for Codex, and it was done in the form of a discussion where I verified everything it said and corrected it where needed, telling it not to write anything for me, just to correct me where I miss things. It overcomplicated a lot of words and was unable to understand some things since it didn't have access to the code files, so I had to clarify a lot. 
I used Codex to code in VS Code, discussing and planning with it before making multiple changes to agent.py. I verified its code before approving it and allowing it to make changes. I did not add any code manually, but I checked its code, reverted, tested it, and asked for changes when needed. I checked the eval and mean score every time before pushing to main. 
It only made changes to the code that I described and asked for through my pseudocode and planning. It made changes to class behavior, last seen info, threat calculation, kiting, rescue, tiebreakers, prioritisation, freeing, and engaging. However, it was hard to validate a lot of it, as it made all the changes I specified at once instead of one by one as I asked, and there were places where it misinterpreted or was unable to think for itself about what was needed, so I would plan with it more before starting and give it rules to start with next time. 

