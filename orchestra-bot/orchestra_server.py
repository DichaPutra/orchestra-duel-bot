"""
Orchestra Server — ZMQ server yang mengimplementasikan protocol JDuelBotClient.

Mode Hybrid (Opsi A + Opsi B):
- Memory-first: LP, Phase, Turn, Hand count dibaca dari game memory (gratis)
- Vision-fallback: kalo memory gagal / data kartu → vision LLM
- Statistik tracking: monitor berapa vision call yang di-save
"""

import json
import os
import logging
import sys
import time
import traceback
from typing import Any, Optional

from jduel_bot import jduel_bot_enums as enums

logger = logging.getLogger("orchestra.server")

# ── MODE PILIHAN ──
# "hybrid" = memory + vision fallback, "memory_only" = pure memory reader
MODE = os.getenv("BOT_MODE", "memory_only").lower()

# Statistik
_server_stats = {
    "commands_processed": 0,
    "memory_lp_reads": 0,
    "memory_phase_reads": 0,
    "vision_board_states": 0,
    "vision_calls_saved": 0,
}


class OrchestraServer:
    """
    ZMQ server yang handle command dari Python client.

    Command yang diimplementasikan:
      - isDueling, isDuelEnded, isMyTurn, isInputting
      - getCurrentPhase, getBoardState, getLP, getCardID, getCardInHand
      - comDoCommand, movePhase, simulateClick
      - waitForInputEnabled, cancelActivationPrompts
      - getWindowResolution, getServerStats
    """

    def __init__(self):
        self.capture = None
        self.input = None
        self.vision = None
        self.window = None
        self.memory_state = None

        # Vision state cache
        self._last_vision_state = None
        self._last_vision_time = 0
        self._vision_cache_ttl = 0.5  # detik

        self._last_lp = 8000
        self._last_phase = 2
        self._last_hand = 5

    def bind_modules(self, capture_mod, vision_mod, input_mod, window_mod, memory_state_mod=None):
        """Bind module references."""
        self.capture = capture_mod
        self.vision = vision_mod
        self.input = input_mod
        self.window = window_mod
        self.memory_state = memory_state_mod

        # Init memory reader kalo available
        global MODE
        if memory_state_mod is not None and hasattr(memory_state_mod, 'try_init_memory'):
            if memory_state_mod.try_init_memory():
                logger.info(f"🔄 Server mode: {MODE.upper()}")
            else:
                logger.warning(f"⚠️ Memory reader init failed. Running in {MODE.upper()} mode anyway.")

    # ── Command dispatch ──

    def handle_command(self, command: str, args: dict) -> dict:
        """Dispatch command ke handler. Return response dict."""
        global _server_stats
        _server_stats["commands_processed"] += 1

        handlers = {
            "isDueling": self._cmd_is_dueling,
            "isDuelEnded": self._cmd_is_duel_ended,
            "isMyTurn": self._cmd_is_my_turn,
            "isInputting": self._cmd_is_inputting,
            "getCurrentPhase": self._cmd_getCurrentPhase,
            "getBoardState": self._cmd_get_board_state,
            "getLP": self._cmd_get_lp,
            "getCardID": self._cmd_get_card_id,
            "getCardInHand": self._cmd_get_hand_size,
            "getHandSize": self._cmd_get_hand_size,
            "comDoCommand": self._cmd_com_do_command,
            "movePhase": self._cmd_move_phase,
            "simulateClick": self._cmd_simulate_click,
            "waitForInputEnabled": self._cmd_wait_for_input,
            "cancelActivationPrompts": self._cmd_cancel_prompts,
            "getWindowResolution": self._cmd_get_window_resolution,
            "getServerStats": self._cmd_get_stats,
            "getTurnNumber": self._cmd_get_turn_number,
            "isOnline": self._cmd_is_online,
            "isDiscardReady": self._cmd_is_discard_ready,
            "discardLeftmostCard": self._cmd_discard_leftmost,
            
            # Compatibility stubs
            "setActivationConfirmation": self._cmd_set_activation_confirmation,
            "getDialogCardList": self._cmd_get_dialog_card_list,
            "getChainData": self._cmd_get_chain_data,
            "getDuelLog": self._cmd_get_duel_log,
            "getLastUsedCardName": self._cmd_get_last_used_card_name,
            "getCardTurn": self._cmd_get_card_turn,
            "getCardFace": self._cmd_get_card_face,
            "comGetCommandMask": self._cmd_com_get_command_mask,
            "getDeckSize": self._cmd_get_deck_size,
            "getPlayerName": self._cmd_get_player_name,
            "specialSummonFromHand": self._cmd_special_summon_from_hand,
            "confirmCardTurn": self._cmd_confirm_card_turn,
            "performTributeSummon": self._cmd_perform_tribute_summon,
            "declareAttack": self._cmd_declare_attack,
            "selectCardsFromDialog": self._cmd_select_cards_from_dialog,
            "clickMyMonsterZone": self._cmd_click_my_monster_zone,
            "setDuelStep": self._cmd_set_duel_step,
            "getMonsterZoneCoordinates": self._cmd_get_monster_zone_coordinates,
        }
        handler = handlers.get(command)
        if handler is None:
            logger.warning(f"⚠️ Command '{command}' not registered. Returning default success response.")
            return {"returnValue": True}

        try:
            return handler(args)
        except Exception as e:
            logger.error("Command %s failed: %s", command, e)
            traceback.print_exc()
            return {"errorMessage": str(e)}

    # ── Helpers ──

    def _get_rect(self):
        """Cari window game."""
        rect = self.window.find_window_rect("Yu-Gi-Oh! Master Duel")
        if rect is None:
            raise RuntimeError("Master Duel window not found")
        return rect

    def _get_screenshot(self):
        """Screenshot window game."""
        rect = self._get_rect()
        if self.capture is None:
            raise RuntimeError("Capture module not bound")
        img = self.capture.capture_window(rect)
        if img is None:
            raise RuntimeError("Failed to capture game window")
        return img, rect

    def _get_vision_state(self, force=False):
        """Dapetin state dari vision (cached)."""
        if self.vision is None:
            return None
        now = time.time()
        cache_age = now - self._last_vision_time
        if not force and self._last_vision_state and cache_age < self._vision_cache_ttl:
            return self._last_vision_state

        try:
            img, rect = self._get_screenshot()
            if self.input is not None:
                self.input.set_window_rect(rect)

            state = self.vision.get_board_state(img)
            if state:
                self._last_vision_state = state
                self._last_vision_time = now
                global _server_stats
                _server_stats["vision_board_states"] += 1
            return state
        except Exception as e:
            logger.error("Failed to get vision state: %s", e)
            return None



    def _get_state_hybrid(self, force_vision=False):
        """
        Hybrid state reader:
        - Jika MODE == "memory_only", murni baca RAM + dummy card names.
        - Jika MODE == "hybrid", baca RAM + panggil Vision untuk nama kartu.
        """
        result = {
            "MY_LP": 8000,
            "OPPONENT_LP": 8000,
            "CURRENT_PHASE": "Main 1",
            "PHASE_VALUE": 2,
            "IS_MY_TURN": True,
            "HAND_COUNT": 5,
            "DUEL_ENDED": False,
            "CARDS_IN_HAND": [],
            "MY_MONSTERS": [],
            "MY_SPELLS_TRAPS": [],
            "MY_GRAVEYARD": [],
            "OPPONENT_MONSTERS": 0,
            "OPPONENT_SPELLS_TRAPS": 0,
            "source": "memory",
        }

        # ── Memory path ──
        memory_ok = False
        if self.memory_state is not None:
            my_lp = self.memory_state.read_lp(0)
            opp_lp = self.memory_state.read_lp(1)
            phase = self.memory_state.read_phase()
            turn = self.memory_state.read_is_my_turn()
            hand = self.memory_state.read_hand_count()

            if my_lp is not None and 0 <= my_lp <= 99999:
                result["MY_LP"] = my_lp
                result["OPPONENT_LP"] = opp_lp if opp_lp is not None else 8000
                _server_stats["memory_lp_reads"] += 1

            if phase is not None and 0 <= phase <= 7:
                result["PHASE_VALUE"] = phase
                phase_names = {0: "Draw", 1: "Standby", 2: "Main 1",
                               3: "Battle", 4: "Main 2", 5: "End"}
                result["CURRENT_PHASE"] = phase_names.get(phase, f"Phase_{phase}")
                _server_stats["memory_phase_reads"] += 1

            if turn is not None:
                result["IS_MY_TURN"] = turn

            if hand is not None and 0 <= hand <= 15:
                result["HAND_COUNT"] = hand

            if result["MY_LP"] == 0:
                result["DUEL_ENDED"] = True

            memory_ok = (my_lp is not None)

        if MODE == "memory_only" or self.vision is None:
            # Pure RAM mode: Generate dummy card names
            result["CARDS_IN_HAND"] = ["Unknown Card"] * result["HAND_COUNT"]
            result["source"] = "memory"

            # Update tracking
            self._last_lp = result["MY_LP"]
            self._last_phase = result["PHASE_VALUE"]
            self._last_hand = result["HAND_COUNT"]
            return result

        # ── Hybrid / Vision Path ──
        need_vision = force_vision or not memory_ok

        # Check if RAM values changed significantly
        if memory_ok:
            if (abs(result["MY_LP"] - self._last_lp) > 0 or
                result["PHASE_VALUE"] != self._last_phase or
                result["HAND_COUNT"] != self._last_hand):
                need_vision = True

        if need_vision:
            vision_state = self._get_vision_state(force=True)
            if vision_state:
                # Override with vision values for accuracy
                for key in ["MY_LP", "OPPONENT_LP", "CURRENT_PHASE", "IS_MY_TURN", "DUEL_ENDED"]:
                    if key in vision_state:
                        result[key] = vision_state[key]
                result["CARDS_IN_HAND"] = vision_state.get("CARDS_IN_HAND", [])
                result["MY_MONSTERS"] = vision_state.get("MY_MONSTERS", [])
                result["MY_SPELLS_TRAPS"] = vision_state.get("MY_SPELLS_TRAPS", [])
                result["MY_GRAVEYARD"] = vision_state.get("MY_GRAVEYARD", [])
                result["OPPONENT_MONSTERS"] = vision_state.get("OPPONENT_MONSTERS", 0)
                result["OPPONENT_SPELLS_TRAPS"] = vision_state.get("OPPONENT_SPELLS_TRAPS", 0)

                result["source"] = "hybrid" if memory_ok else "vision"

                # Update tracking
                self._last_lp = result["MY_LP"]
                self._last_phase = result["PHASE_VALUE"]
                self._last_hand = result["HAND_COUNT"]
        else:
            # Use cached vision details
            if self._last_vision_state:
                result["CARDS_IN_HAND"] = self._last_vision_state.get("CARDS_IN_HAND", [])
                result["MY_MONSTERS"] = self._last_vision_state.get("MY_MONSTERS", [])
                result["MY_SPELLS_TRAPS"] = self._last_vision_state.get("MY_SPELLS_TRAPS", [])
                result["MY_GRAVEYARD"] = self._last_vision_state.get("MY_GRAVEYARD", [])
                result["OPPONENT_MONSTERS"] = self._last_vision_state.get("OPPONENT_MONSTERS", 0)
                result["OPPONENT_SPELLS_TRAPS"] = self._last_vision_state.get("OPPONENT_SPELLS_TRAPS", 0)
                result["source"] = "memory+cache"
                _server_stats["vision_calls_saved"] += 1

        return result

    # ── Command implementations ──

    def _cmd_is_dueling(self, args) -> dict:
        """Cek apakah sedang dalam duel (Memory + Vision fallback)."""
        if self.memory_state is not None:
            my_lp = self.memory_state.read_lp(0)
            if my_lp is not None:
                return {"returnValue": my_lp > 0}
        if MODE == "hybrid":
            state = self._get_vision_state()
            if state:
                return {"returnValue": not state.get("DUEL_ENDED", True)}
        return {"returnValue": False}

    def _cmd_is_duel_ended(self, args) -> dict:
        """Cek apakah duel sudah selesai (Memory + Vision fallback)."""
        if self.memory_state is not None:
            my_lp = self.memory_state.read_lp(0)
            if my_lp is not None and my_lp == 0:
                return {"returnValue": True}
        if MODE == "hybrid":
            state = self._get_vision_state()
            if state:
                return {"returnValue": state.get("DUEL_ENDED", False)}
        return {"returnValue": False}

    def _cmd_getCurrentPhase(self, args) -> dict:
        """Dapetin phase sekarang (Memory + Vision fallback)."""
        if self.memory_state is not None:
            phase = self.memory_state.read_phase()
            if phase is not None and 0 <= phase <= 7:
                return {"returnValue": phase}
        if MODE == "hybrid":
            state = self._get_vision_state()
            if state:
                phase_str = (state.get("CURRENT_PHASE", "") or "").lower().strip()
                phase_names = {
                    "draw": 0, "standby": 1, "main 1": 2, "main1": 2,
                    "main phase 1": 2, "battle": 3, "main 2": 4, "main2": 4,
                    "main phase 2": 4, "end": 5,
                }
                return {"returnValue": phase_names.get(phase_str, 2)}
        return {"returnValue": enums.Phase.Main1.value}

    def _cmd_is_my_turn(self, args) -> dict:
        """Cek apakah giliran kita (Memory + Vision fallback)."""
        if self.memory_state is not None:
            turn = self.memory_state.read_is_my_turn()
            if turn is not None:
                return {"returnValue": bool(turn)}
        if MODE == "hybrid":
            state = self._get_vision_state()
            if state:
                return {"returnValue": bool(state.get("IS_MY_TURN", True))}
        return {"returnValue": True}

    def _cmd_is_inputting(self, args) -> dict:
        """Cek apakah player bisa input."""
        return {"returnValue": True}

    def _cmd_get_current_phase(self, args) -> dict:
        """Dapetin phase sekarang (Memory + Vision fallback)."""
        if self.memory_state is not None:
            phase = self.memory_state.read_phase()
            if phase is not None and 0 <= phase <= 7:
                return {"returnValue": phase}
        if MODE == "hybrid":
            state = self._get_vision_state()
            if state:
                phase_str = (state.get("CURRENT_PHASE", "") or "").lower().strip()
                phase_names = {
                    "draw": 0, "standby": 1, "main 1": 2, "main1": 2,
                    "main phase 1": 2, "battle": 3, "main 2": 4, "main2": 4,
                    "main phase 2": 4, "end": 5,
                }
                return {"returnValue": phase_names.get(phase_str, 2)}
        return {"returnValue": enums.Phase.Main1.value}

    def _cmd_get_board_state(self, args) -> dict:
        """Dapetin full board state (Memory + Vision hybrid)."""
        state = self._get_state_hybrid()
        return {"returnValue": _convert_state_to_client_format(state)}

    def _cmd_get_lp(self, args) -> dict:
        """Dapetin LP (Memory + Vision fallback)."""
        player = args.get("player", 0)
        if self.memory_state is not None:
            lp = self.memory_state.read_lp(player)
            if lp is not None and 0 <= lp <= 99999:
                return {"returnValue": int(lp)}
        if MODE == "hybrid":
            state = self._get_vision_state()
            if state:
                key = "MY_LP" if player == 0 else "OPPONENT_LP"
                return {"returnValue": int(state.get(key, 8000))}
        return {"returnValue": 8000}

    def _cmd_get_card_id(self, args) -> dict:
        """Dapetin card ID (Memory only - always 0)."""
        return {"returnValue": 0}

    def _cmd_get_hand_size(self, args) -> dict:
        """Dapetin jumlah kartu di hand (Memory + Vision fallback)."""
        player = args.get("player", 0)
        if player == 0 and self.memory_state is not None:
            hand = self.memory_state.read_hand_count()
            if hand is not None and 0 <= hand <= 15:
                return {"returnValue": int(hand)}
        if MODE == "hybrid":
            state = self._get_vision_state()
            if state and "CARDS_IN_HAND" in state:
                return {"returnValue": len(state["CARDS_IN_HAND"])}
        return {"returnValue": 0}

    def _cmd_com_do_command(self, args) -> dict:
        """Execute game command via klik (sama kayak sebelumnya)."""
        player = args.get("player", 0)
        position = args.get("position", 0)
        index = args.get("index", 0)
        command_id = args.get("commandId", 0)

        logger.info("comDoCommand: player=%d pos=%d idx=%d cmd=%d",
                    player, position, index, command_id)

        if position == 13:  # Hand
            self.input.click_hand_card(index)
            time.sleep(0.8)
            if command_id in (3, 4, 7):  # Action, Summon, Set
                time.sleep(0.3)
                self.input.confirm()
        elif position in range(0, 5):  # Monster zone
            self.input.click_monster_zone(position)
        elif position in range(7, 12):  # Spell/trap zone
            self.input.click_spell_zone(position - 7)
        elif position == 12:  # Field
            self.input.click("field_zone")
        elif position == 16:  # Grave
            self.input.click("gy")
        elif command_id == 12:  # Decide
            self.input.confirm()
        elif command_id == 0:  # Attack
            self.input.battle_phase()
        else:
            self.input.confirm()

        return {"returnValue": True}

    def _cmd_move_phase(self, args) -> dict:
        """Pindah phase."""
        phase = args.get("phase", 5)
        if phase == 3:  # Battle
            self.input.battle_phase()
        elif phase == 4:  # Main 2
            self.input.click("main_phase_2")
        elif phase == 5:  # End
            self.input.end_turn()
        time.sleep(0.8)
        return {"returnValue": True}

    def _cmd_simulate_click(self, args) -> dict:
        """Klik di koordinat tertentu."""
        self.input.click(args.get("x", 640), args.get("y", 360))
        return {"returnValue": True}

    def _cmd_wait_for_input(self, args) -> dict:
        """Tunggu beberapa saat."""
        time.sleep(1.5)
        return {"returnValue": True}

    def _cmd_cancel_prompts(self, args) -> dict:
        """Cancel activation prompts."""
        self.input.cancel_prompts()
        return {"returnValue": True}

    def _cmd_get_window_resolution(self, args) -> dict:
        """Dapetin resolusi window game."""
        try:
            rect = self._get_rect()
            w, h = self.window.get_game_resolution(rect)
            return {"returnValue": {"x": w, "y": h}}
        except RuntimeError:
            return {"returnValue": {"x": 1280, "y": 720}}

    def _cmd_get_stats(self, args) -> dict:
        """Return server statistics."""
        return {"returnValue": _server_stats}

    def _cmd_get_turn_number(self, args) -> dict:
        """Get current turn number (always 1 for simplicity)."""
        return {"returnValue": 1}

    def _cmd_is_online(self, args) -> dict:
        """Check if online duel (always False for solo)."""
        return {"returnValue": False}

    def _cmd_is_discard_ready(self, args) -> dict:
        """Check if discard prompt is active (always False for simplicity)."""
        return {"returnValue": False}

    def _cmd_discard_leftmost(self, args) -> dict:
        """Discard leftmost card."""
        self.input.click_hand_card(0)
        time.sleep(0.5)
        self.input.confirm()
        return {"returnValue": True}

    def _cmd_set_activation_confirmation(self, args) -> dict:
        mode = args.get("activateConfirmMode", 0)
        logger.info("setActivationConfirmation: mode=%s", mode)
        return {"returnValue": True}

    def _cmd_get_dialog_card_list(self, args) -> dict: 
        return {"returnValue": []}

    def _cmd_get_chain_data(self, args) -> dict:
        return {"returnValue": []}

    def _cmd_get_duel_log(self, args) -> dict:
        return {"returnValue": []}

    def _cmd_get_last_used_card_name(self, args) -> dict:
        return {"returnValue": ""}

    def _cmd_get_card_turn(self, args) -> dict:
        return {"returnValue": 0}

    def _cmd_get_card_face(self, args) -> dict:
        return {"returnValue": 0}

    def _cmd_com_get_command_mask(self, args) -> dict:
        return {"returnValue": 0}

    def _cmd_get_deck_size(self, args) -> dict:
        return {"returnValue": 40}

    def _cmd_get_player_name(self, args) -> dict:
        return {"returnValue": "Player"}

    def _cmd_special_summon_from_hand(self, args) -> dict:
        index = args.get("index", 0)
        position = args.get("position", 0)
        logger.info("specialSummonFromHand: index=%d position=%d", index, position)
        if self.input is not None:
            self.input.click_hand_card(index)
            time.sleep(0.8)
            self.input.confirm()
        return {"returnValue": True}

    def _cmd_confirm_card_turn(self, args) -> dict:
        return {"returnValue": True}

    def _cmd_perform_tribute_summon(self, args) -> dict:
        return {"returnValue": True}

    def _cmd_declare_attack(self, args) -> dict:
        position = args.get("position", 0)
        target = args.get("targetPosition", None)
        logger.info("declareAttack: position=%d target=%s", position, target)
        if self.input is not None:
            self.input.click_monster_zone(position)
            time.sleep(0.8)
            if target is not None:
                self.input.click_monster_zone(target)
            else:
                self.input.click(640, 200)
            time.sleep(0.8)
        return {"returnValue": True}

    def _cmd_select_cards_from_dialog(self, args) -> dict:
        return {"returnValue": True}

    def _cmd_click_my_monster_zone(self, args) -> dict:
        return {"returnValue": True}

    def _cmd_set_duel_step(self, args) -> dict:
        return {"returnValue": True}

    def _cmd_get_monster_zone_coordinates(self, args) -> dict:
        return {"returnValue": {"x": 640, "y": 360}}


def _convert_state_to_client_format(state: dict) -> dict:
    """Convert state dict ke format DuelCardState."""
    hand_cards = []
    for card_name in state.get("CARDS_IN_HAND", []):
        hand_cards.append({
            "id": 0, "name": card_name,
            "type": "Card", "face": 0,
            "position": 13, "atk": 0, "defense": 0,
            "command_bits": []
        })

    monsters = []
    for i, m in enumerate(state.get("MY_MONSTERS", [])):
        if isinstance(m, dict):
            monsters.append({
                "id": 0, "name": m.get("name", f"Monster {i}"),
                "type": "Monster",
                "face": 0 if m.get("face-up", True) else 1,
                "position": i, "atk": m.get("atk", 0),
                "defense": m.get("def", 0),
                "command_bits": []
            })
        elif m:
            monsters.append({
                "id": 0, "name": str(m),
                "type": "Monster", "face": 1,
                "position": i, "atk": 0, "defense": 0,
                "command_bits": []
            })
        else:
            monsters.append(None)

    while len(monsters) < 5:
        monsters.append(None)

    return {
        "source": state.get("source", "unknown"),
        "player_card_states": {
            "0": {
                "hand": hand_cards,
                "monsters": monsters,
                "spells_and_traps": _pad_list(
                    [{"id": 0, "name": str(s), "type": "Spell",
                      "face": 1, "position": i}
                     for i, s in enumerate(state.get("MY_SPELLS_TRAPS", []))
                     if s is not None], 5),
                "field_spell": None,
                "main_deck": [],
                "extra_deck": [],
                "graveyard": [{"id": 0, "name": str(c), "type": "Card"}
                              for c in state.get("MY_GRAVEYARD", [])],
                "banished": [],
                "xyz_materials": [],
            },
            "1": {
                "hand": [],
                "monsters": _pad_list(
                    [{} for _ in range(state.get("OPPONENT_MONSTERS", 0))], 5),
                "spells_and_traps": _pad_list(
                    [{} for _ in range(state.get("OPPONENT_SPELLS_TRAPS", 0))], 5),
                "field_spell": None,
                "main_deck": [],
                "extra_deck": [],
                "graveyard": [],
                "banished": [],
                "xyz_materials": [],
            }
        }
    }


def _pad_list(lst, size):
    """Pad list ke size tertentu dengan None."""
    result = list(lst)[:size]
    while len(result) < size:
        result.append(None)
    return result


def run_server(port: int = 5555, server_instance: OrchestraServer = None):
    """
    Run ZMQ server. Blocking.

    Usage:
        server = OrchestraServer()
        server.bind_modules(input, window, memory_state)
        run_server(5555, server)
    """
    import zmq

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    address = f"tcp://127.0.0.1:{port}"
    socket.bind(address)
    logger.info("Orchestra Server listening on %s", address)

    stats_interval = 60  # Log stats setiap N detik
    last_stats_log = time.time()

    while True:
        try:
            message = socket.recv_string()
            request = json.loads(message)
            command = request.get("command", "")
            args = request.get("arguments", {})

            logger.debug("→ %s %s", command, args)
            response = server_instance.handle_command(command, args)
            socket.send_string(json.dumps(response))
            logger.debug("← %s", response)

            # Periodic stats
            now = time.time()
            if now - last_stats_log > stats_interval:
                global _server_stats
                saved = _server_stats.get("vision_calls_saved", 0)
                made = _server_stats.get("vision_board_states", 0)
                total = saved + made
                pct = round(saved / max(total, 1) * 100, 1) if total > 0 else 0
                logger.info(
                    f"📊 Stats: {_server_stats['commands_processed']} commands | "
                    f"Memory LP reads: {_server_stats['memory_lp_reads']} | "
                    f"Memory Phase reads: {_server_stats['memory_phase_reads']} | "
                    f"Vision calls: {made} | "
                    f"Saved: {saved} ({pct}%)"
                )
                last_stats_log = now

        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            break
        except Exception as e:
            logger.error("Server error: %s", e)
            traceback.print_exc()
            try:
                socket.send_string(json.dumps({"errorMessage": str(e)}))
            except Exception:
                pass

    socket.close()
    context.term()
