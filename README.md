# Trophy Dilution Forecaster v7

[![bounty](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/rohitchanuwu69-bot/gta6-trophy-rarity-forecast-01-v7/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/rohitchanuwu69-bot/gta6-trophy-rarity-forecast-01-v7/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)

Forecasts every GTA VI trophy's Exophase earn rate at a case's target, for the [make.fun bounty](https://make.fun/bounty/gta6-trophy-rarity-forecast-01).

On a flat launch-night history it models the first refresh in whole players: tracked players jump, earned counts stay frozen except the trophies in the top three distinct rate values, which gain newcomers at about 28%. On a moving history it fits growth in log time for players and earned counts. Python 3.13 standard library only, deterministic, no network.

Run it with `MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py` from the repository root.
