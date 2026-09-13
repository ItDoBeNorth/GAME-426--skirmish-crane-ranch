"""A role-based Season 1 agent for Skirmish at Crane Reach.

Each unit runs a separate instance of this class. Read ``environment.md`` beside this file for
the rules, helpers, and later-season mechanics. Prepare episode state in ``reset``; the
constructor takes no arguments. Movement always comes from the action mask: this agent scores
complete legal paths rather than recreating movement rules.
"""

from __future__ import annotations

import random
from typing import Iterable

from sandbox.crane import action, me, tile, units, visible
from sandbox.observation_types import AxialPosition, SkirmishAction, SkirmishObservation, VisibleUnit


Position = dict[str, int]
PathOption = tuple[int, AxialPosition]


class Agent:
    """Use archer kiting and local melee support to contest the center."""

    def reset(self, seed, observation) -> None:
        # Called once before each match. The opening observation is available here for
        # precomputation outside the decision clock. Each unit's memory remains private.
        self._activation = 0
        self._rng = random.Random(seed)
        self._last_seen_enemies: dict[str, tuple[str, Position]] = {}
        self._last_seen_allies: dict[str, Position] = {}
        self._enemy_seen_on: dict[str, int] = {}

    def act(self, observation: SkirmishObservation) -> SkirmishAction:
        self._activation += 1
        enemies = visible.enemies(observation)
        allies = visible.allies(observation)
        self._remember(enemies, allies)
        paths = self._paths(observation)
        if me.unit_type(observation) == "archer":
            return self._act_archer(observation, paths, enemies, allies)
        return self._act_melee(observation, paths, enemies, allies)

    def _remember(self, enemies: Iterable[VisibleUnit], allies: Iterable[VisibleUnit]) -> None:
        for enemy in enemies:
            self._last_seen_enemies[enemy["unit_id"]] = (enemy["type"], self._copy(enemy["position"]))
            self._enemy_seen_on[enemy["unit_id"]] = self._activation
        for ally in allies:
            self._last_seen_allies[ally["unit_id"]] = self._copy(ally["position"])

    def _act_archer(self, observation: SkirmishObservation, paths: list[PathOption], enemies: list[VisibleUnit], allies: list[VisibleUnit]) -> SkirmishAction:
        target = self._select_target(observation, paths, enemies)
        if target is not None:
            firing_paths = self._attack_paths(paths, target, "archer")
            if firing_paths:
                melee_threats = [enemy for enemy in enemies if enemy["type"] in {"cavalry", "footman"}]
                choices = self._safe_paths(firing_paths, melee_threats) or firing_paths
                # Kite while preserving the shot: prefer the farthest firing endpoint.
                path = max(choices, key=lambda option: (self._distance(option[1], target["position"]), -option[0]))
                return self._order(path[0], target["unit_id"], observation)
        enemy_goal = self._last_seen_goal("archer")
        if allies:
            return self._order(
                self._advance_with_visible_ally(observation, paths, allies, enemy_goal or tile.at_center(observation)),
                None,
                observation,
            )
        goal = enemy_goal or self._ally_goal(observation, allies) or tile.at_center(observation)
        return self._order(self._toward(paths, goal), None, observation)

    def _act_melee(self, observation: SkirmishObservation, paths: list[PathOption], enemies: list[VisibleUnit], allies: list[VisibleUnit]) -> SkirmishAction:
        unit_type = me.unit_type(observation)
        attack_range = units.STATS[unit_type].attack_range
        adjacent = [enemy for enemy in enemies if self._distance(me.position(observation), enemy["position"]) <= attack_range]
        if adjacent:
            target = self._select_target(observation, paths, adjacent)
            return self._order(0, target["unit_id"] if target else None, observation)

        archer_threats = self._archer_threats(enemies)
        if archer_threats:
            opportunistic = self._select_target(observation, paths, [enemy for enemy in enemies if enemy["type"] in {"cavalry", "footman"}])
            if opportunistic is not None:
                attack_paths = self._attack_paths(paths, opportunistic, unit_type)
                if attack_paths:
                    return self._order(self._toward_option(attack_paths, opportunistic["position"])[0], opportunistic["unit_id"], observation)
            return self._archer_response(observation, paths, archer_threats)

        target = self._select_target(observation, paths, [enemy for enemy in enemies if enemy["type"] in {"cavalry", "footman"}])
        if target is not None:
            attack_paths = self._attack_paths(paths, target, unit_type)
            if attack_paths:
                return self._order(self._toward_option(attack_paths, target["position"])[0], target["unit_id"], observation)
            safer_paths = self._safe_paths(paths, [target])
            return self._order(self._toward(safer_paths or paths, target["position"]), None, observation)
        return self._melee_rendezvous(observation, paths, allies)

    def _archer_response(self, observation: SkirmishObservation, paths: list[PathOption], threats: list[tuple[str, Position]]) -> SkirmishAction:
        safe_paths = self._safe_memory_paths(paths, threats)
        if me.unit_type(observation) == "footman":
            return self._order(self._flee(safe_paths or paths, threats), None, observation)
        # Cavalry's approved one-turn proxy: escape, else engage if possible, else partially engage.
        if safe_paths:
            return self._order(self._flee(safe_paths, threats), None, observation)
        target = self._select_target(observation, paths, [enemy for enemy in visible.enemies(observation) if enemy["type"] == "archer"])
        if target is not None:
            attack_paths = self._attack_paths(paths, target, "cavalry")
            if attack_paths:
                return self._order(self._toward_option(attack_paths, target["position"])[0], target["unit_id"], observation)
            return self._order(self._toward(paths, target["position"]), None, observation)
        return self._order(self._flee(paths, threats), None, observation)

    def _melee_rendezvous(self, observation: SkirmishObservation, paths: list[PathOption], allies: list[VisibleUnit]) -> SkirmishAction:
        enemy_goal = self._last_seen_non_archer_goal()
        if allies:
            return self._order(
                self._advance_with_visible_ally(observation, paths, allies, enemy_goal or tile.at_center(observation)),
                None,
                observation,
            )
        ally_goal = self._ally_goal(observation, allies)
        if ally_goal is not None:
            return self._order(self._toward(paths, enemy_goal or ally_goal), None, observation)
        return self._order(self._toward(paths, enemy_goal or tile.at_center(observation)), None, observation)

    def _advance_with_visible_ally(
        self, observation: SkirmishObservation, paths: list[PathOption], allies: Iterable[VisibleUnit], goal: Position
    ) -> int:
        """Advance toward goal while keeping at least one currently visible ally in vision."""
        vision = units.STATS[me.unit_type(observation)].vision
        linked_paths = [
            path
            for path in paths
            if any(self._distance(path[1], ally["position"]) <= vision for ally in allies)
        ]
        # Staying put is always linked to an ally already visible, but retain the general fallback
        # so this helper remains safe if future rules change what visibility means.
        return self._toward(linked_paths or paths, goal)

    def _paths(self, observation: SkirmishObservation) -> list[PathOption]:
        here = me.position(observation)
        return [(path_id, tile.at_path_end(here, path_id)) for path_id in action.legal_paths(observation)]

    def _select_target(self, observation: SkirmishObservation, paths: list[PathOption], candidates: Iterable[VisibleUnit]) -> VisibleUnit | None:
        candidates = list(candidates)
        if not candidates:
            return None
        own_range = units.STATS[me.unit_type(observation)].attack_range
        allies = visible.allies(observation)
        type_priority = {"archer": 0, "cavalry": 1, "footman": 2}

        def score(enemy: VisibleUnit) -> tuple[int, int, int, int]:
            attackable = any(self._distance(end, enemy["position"]) <= own_range for _, end in paths)
            threatens_ally = any(self._distance(enemy["position"], ally["position"]) <= units.STATS[enemy["type"]].attack_range for ally in allies)
            return (-int(attackable), -int(threatens_ally), type_priority[enemy["type"]], self._distance(me.position(observation), enemy["position"]))

        return min(candidates, key=score)

    def _attack_paths(self, paths: Iterable[PathOption], target: VisibleUnit, attacker_type: str) -> list[PathOption]:
        return [path for path in paths if self._distance(path[1], target["position"]) <= units.STATS[attacker_type].attack_range]

    def _safe_paths(self, paths: Iterable[PathOption], threats: Iterable[VisibleUnit]) -> list[PathOption]:
        return self._safe_memory_paths(paths, [(threat["type"], threat["position"]) for threat in threats])

    def _safe_memory_paths(self, paths: Iterable[PathOption], threats: Iterable[tuple[str, Position]]) -> list[PathOption]:
        threats = list(threats)
        return [path for path in paths if all(self._distance(path[1], position) > self._threat_range(kind) for kind, position in threats)]

    def _archer_threats(self, enemies: Iterable[VisibleUnit]) -> list[tuple[str, Position]]:
        threats = [(enemy["type"], enemy["position"]) for enemy in enemies if enemy["type"] == "archer"]
        visible_ids = {enemy["unit_id"] for enemy in enemies}
        for unit_id, (kind, position) in self._last_seen_enemies.items():
            if kind == "archer" and unit_id not in visible_ids and self._activation - self._enemy_seen_on[unit_id] == 1:
                threats.append((kind, position))
        return threats

    def _ally_goal(self, observation: SkirmishObservation, allies: Iterable[VisibleUnit]) -> Position | None:
        choices = [(ally["type"], ally["position"]) for ally in allies] or [("", position) for position in self._last_seen_allies.values()]
        if not choices:
            return None
        return self._copy(min(choices, key=lambda choice: (self._distance(me.position(observation), choice[1]), choice[0] != "cavalry"))[1])

    def _last_seen_goal(self, unit_type: str) -> Position | None:
        positions = [position for kind, position in self._last_seen_enemies.values() if kind == unit_type]
        return self._copy(positions[0]) if positions else None

    def _last_seen_non_archer_goal(self) -> Position | None:
        positions = [position for kind, position in self._last_seen_enemies.values() if kind != "archer"]
        return self._copy(self._rng.choice(positions)) if positions else None

    def _toward(self, paths: Iterable[PathOption], goal: Position) -> int:
        return self._toward_option(paths, goal)[0]

    def _toward_option(self, paths: Iterable[PathOption], goal: Position) -> PathOption:
        return min(paths, key=lambda option: (self._distance(option[1], goal), option[0]))

    def _flee(self, paths: Iterable[PathOption], threats: Iterable[tuple[str, Position]]) -> int:
        threats = list(threats)
        return max(paths, key=lambda option: (min(self._distance(option[1], position) - self._threat_range(kind) for kind, position in threats), sum(self._distance(option[1], position) for _, position in threats), -option[0]))[0]

    def _order(self, path_id: int, target_id: str | None, observation: SkirmishObservation) -> SkirmishAction:
        if path_id == 0:
            return action.stay(target_id, observation) if target_id else action.stay()
        return action.move(path_id, target_id, observation) if target_id else action.move(path_id)

    @staticmethod
    def _copy(position: AxialPosition) -> Position:
        return {"q": position["q"], "r": position["r"]}

    @staticmethod
    def _distance(first: AxialPosition, second: AxialPosition) -> int:
        return tile.distance(first, second)

    @staticmethod
    def _threat_range(unit_type: str) -> int:
        stats = units.STATS[unit_type]
        return stats.movement_points + stats.attack_range

    # Original template TODO notes, retained as course-reference milestones:
    # TODO(you) (completed): this unit stood still when forward was blocked. The agent now scores
    # every legal path and can take an alternate route toward its current strategic goal.
    # TODO(you) (completed): walking toward the nearest enemy was the entire strategy. Archer,
    # cavalry, and footman now use separate kiting, flee/engage, and support behavior.
    # TODO(you) (completed): only single steps were tried. Legal paths of up to four steps are now
    # evaluated, so cavalry can use its full movement allowance.

    # Optional: a reinforcement-learning hook called after every step with that step's
    # transition. Its time counts against the timing and episode budget. The order argument is
    # what act returned. It is named order so it does not shadow the action helpers.
    #
    # def learn(self, observation, order: SkirmishAction, reward: float, terminated: bool) -> None:
    #     ...

    # Optional: messaging. Season settings enable it from Season 3 onward. When enabled, chat runs
    # after a unit chooses its order and receives messages that arrived since its previous
    # activation. Return each message with a recipient and text. Use None to broadcast to both
    # sides, or a player id such as "player_2", not a unit id, to send directly to one ally. The
    # rosters in the observation map each player to its unit. By default, text is limited to 200
    # characters.
    # A direct message reaches its allied unit at its next activation, after that unit chooses its
    # own order. Every message is recorded and shown in replays, so nothing you send is ever secret.
    # Return nothing to stay silent.
    #
    # def chat(self, inbox: list[dict]) -> list[dict] | None:
    #     ...
