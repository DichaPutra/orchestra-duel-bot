"""
LLM Duel Bot — Decides moves using LLM based on text game states.
Supports Gemini, OpenAI, DeepSeek, OpenRouter, and Groq.
"""
import logging
import time
import os
import re
import json
import requests
from pathlib import Path

from jduel_bot.jduel_bot_client import JDuelBotClient
from jduel_bot import jduel_bot_enums as enums

logger = logging.getLogger("orchestra.bot.llm")

# Fallback prompts if txt files are missing
DEFAULT_SYSTEM_PROMPT = """You are an AI playing Yu-Gi-Oh! Master Duel.
Decide on ONE action from: SUMMON, SPECIAL_SUMMON, ACTIVATE_HAND, SET_MAGIC, ACTIVATE_FIELD, ACTIVATE_MONSTER_HAND, ACTIVATE_MONSTER_FIELD, ATTACK, MOVE_PHASE, UNEXPECTED_PROMPT, SURRENDER, WAIT.
Return a valid JSON object only:
{
  "thought": "Tactical reason",
  "action": "ACTION_NAME",
  "arguments": { ... }
}"""

def load_prompt_file(filename: str, fallback: str) -> str:
    """Load prompt content from file or fallback if not found."""
    try:
        path = Path(__file__).parent.parent / "prompts" / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to load prompt file %s: %s", filename, e)
    return fallback

def format_board_state_to_text(client: JDuelBotClient, board_state: enums.DuelCardState) -> str:
    """Format DuelCardState into text representation for LLM."""
    try:
        turn = client.get_turn_number()
    except Exception:
        turn = 1
    
    try:
        phase = client.get_current_phase().name
    except Exception:
        phase = "Main1"

    try:
        my_lp = client.get_lp(enums.Player.Myself)
        opp_lp = client.get_lp(enums.Player.Opponent)
    except Exception:
        my_lp = 8000
        opp_lp = 8000

    # Hand
    hand = board_state.player_card_states[enums.Player.Myself].hand
    hand_desc = []
    for i, card in enumerate(hand):
        name = card.name if card and card.name else "Unknown Card"
        hand_desc.append(f"Index {i}: {name}")
    hand_str = "[" + ", ".join(hand_desc) + "]" if hand_desc else "[]"

    # Monsters
    my_monsters = board_state.player_card_states[enums.Player.Myself].monsters
    mon_desc = []
    for i, mon in enumerate(my_monsters):
        if mon is not None:
            face = "face-up" if mon.face == enums.CardFace.FaceUp else "face-down"
            pos = "Attack" if mon.turn == enums.CardTurn.Attack else "Defense"
            mon_desc.append(f"Zone {i}: {mon.name} ({face}, {pos}, ATK: {mon.atk}, DEF: {mon.defense})")
        else:
            mon_desc.append(f"Zone {i}: Empty")

    # Spells and Traps
    my_st = board_state.player_card_states[enums.Player.Myself].spells_and_traps
    st_desc = []
    for i, st in enumerate(my_st):
        zone_idx = 7 + i
        if st is not None:
            face = "face-up" if st.face == enums.CardFace.FaceUp else "face-down"
            st_desc.append(f"Zone {zone_idx}: {st.name} ({face})")
        else:
            st_desc.append(f"Zone {zone_idx}: Empty")

    # Graveyard
    gy = board_state.player_card_states[enums.Player.Myself].graveyard
    gy_desc = [card.name for card in gy if card is not None]
    gy_str = "[" + ", ".join(gy_desc) + "]" if gy_desc else "[]"

    # Opponent stats
    opp_state = board_state.player_card_states[enums.Player.Opponent]
    opp_monsters_count = sum(1 for m in opp_state.monsters if m is not None)
    opp_st_count = sum(1 for s in opp_state.spells_and_traps if s is not None)

    # Active Dialog/Prompt
    try:
        dialog_cards = client.get_dialog_card_list()
    except Exception:
        dialog_cards = []
    dialog_str = str(dialog_cards) if dialog_cards else "None"

    # Assemble state text
    text_state = (
        f"Current Turn: {turn}\n"
        f"My LP: {my_lp}\n"
        f"Opponent LP: {opp_lp}\n"
        f"Current Phase: {phase}\n"
        f"My Hand: {hand_str}\n"
        f"My Monsters: {mon_desc}\n"
        f"My Spells/Traps: {st_desc}\n"
        f"My Graveyard: {gy_str}\n"
        f"Opponent Monsters Count: {opp_monsters_count}\n"
        f"Opponent Spells/Traps Count: {opp_st_count}\n"
        f"Is Active Dialog: {dialog_str}"
    )
    return text_state

def query_llm(system_prompt: str, examples_prompt: str, text_state: str) -> str:
    """Send prompts and state to configured LLM provider."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    logger.info("Querying LLM using provider: %s", provider)

    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not key:
            raise ValueError("GEMINI_API_KEY is not set.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": f"{system_prompt}\n\nExamples:\n{examples_prompt}\n\nCurrent Board State:\n{text_state}"}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        }
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    elif provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not key:
            raise ValueError("OPENAI_API_KEY is not set.")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Examples:\n{examples_prompt}\n\nCurrent Board State:\n{text_state}"}
            ],
            "temperature": 0.2
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    elif provider == "deepseek":
        key = os.getenv("DEEPSEEK_API_KEY", "")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        if not key:
            raise ValueError("DEEPSEEK_API_KEY is not set.")
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Examples:\n{examples_prompt}\n\nCurrent Board State:\n{text_state}"}
            ],
            "temperature": 0.2
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    elif provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY", "")
        model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
        if not key:
            raise ValueError("OPENROUTER_API_KEY is not set.")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Examples:\n{examples_prompt}\n\nCurrent Board State:\n{text_state}"}
            ],
            "temperature": 0.2
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    elif provider == "groq":
        key = os.getenv("GROQ_API_KEY", "")
        model = os.getenv("GROQ_MODEL", "llama3-70b-8192")
        if not key:
            raise ValueError("GROQ_API_KEY is not set.")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Examples:\n{examples_prompt}\n\nCurrent Board State:\n{text_state}"}
            ],
            "temperature": 0.2
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def clean_and_parse_json(text: str) -> dict:
    """Parse JSON and strip any markdown wraps."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise

def execute_action(client: JDuelBotClient, action: str, args: dict):
    """Map action to client function call."""
    action = action.upper()
    if action == "SUMMON":
        hand_index = int(args["hand_index"])
        zone = int(args.get("zone", 2))
        client.normal_summon_monster(hand_index, enums.CardPosition(zone))

    elif action == "SPECIAL_SUMMON":
        hand_index = int(args["hand_index"])
        zone = int(args.get("zone", 2))
        client.special_summon_monster_from_hand(hand_index, enums.CardPosition(zone))

    elif action == "ACTIVATE_HAND":
        hand_index = int(args["hand_index"])
        zone = int(args.get("zone", 9))
        client.activate_spell_or_trap_from_hand(hand_index, enums.CardPosition(zone))

    elif action == "SET_MAGIC":
        hand_index = int(args["hand_index"])
        zone = int(args.get("zone", 9))
        client.set_spell_or_trap_from_hand(hand_index, enums.CardPosition(zone))

    elif action == "ACTIVATE_FIELD":
        zone = int(args["zone"])
        client.activate_spell_or_trap_from_field(enums.CardPosition(zone))

    elif action == "ACTIVATE_MONSTER_HAND":
        hand_index = int(args["hand_index"])
        client.activate_monster_effect_from_hand(hand_index)

    elif action == "ACTIVATE_MONSTER_FIELD":
        zone = int(args["zone"])
        client.activate_monster_effect_from_field(enums.CardPosition(zone))

    elif action == "ATTACK":
        zone = int(args["zone"])
        target_zone = args.get("target_zone")
        target_pos = enums.CardPosition(int(target_zone)) if target_zone is not None else None
        client.declare_attack(enums.CardPosition(zone), target_pos)

    elif action == "MOVE_PHASE":
        phase_str = args.get("phase", "End").strip()
        phase_map = {
            "Draw": enums.Phase.Draw,
            "Standby": enums.Phase.Standby,
            "Main1": enums.Phase.Main1,
            "Battle": enums.Phase.Battle,
            "Main2": enums.Phase.Main2,
            "End": enums.Phase.End
        }
        target_phase = phase_map.get(phase_str, enums.Phase.End)
        client.move_phase(target_phase)

    elif action == "UNEXPECTED_PROMPT":
        dialog_card_name = args.get("dialog_card_name")
        dialog_card_index = args.get("dialog_card_index")
        if dialog_card_name:
            client.select_card_from_dialog(enums.CardSelection(card_name=dialog_card_name))
        elif dialog_card_index is not None:
            client.select_card_from_dialog(enums.CardSelection(card_index=int(dialog_card_index)))
        else:
            client.select_card_from_dialog(enums.CardSelection(card_index=0))

    elif action == "SURRENDER":
        client.surrender_duel()

    elif action == "WAIT":
        time.sleep(2)

    else:
        logger.warning("Action %s not recognized, executing WAIT fallback", action)
        time.sleep(2)

def run():
    """Main loop for the LLM Bot."""
    client = JDuelBotClient("tcp://127.0.0.1:5555")
    logger.info("LLM Duel Bot initialized")

    time.sleep(2)

    consecutive_failures = 0
    max_consecutive_failures = 3

    while True:
        try:
            # Check if dueling
            if not client.is_dueling():
                logger.info("Waiting for duel to start...")
                time.sleep(3)
                consecutive_failures = 0
                continue

            # Check if duel ended
            if client.is_duel_ended():
                logger.info("Duel ended. Exiting duel...")
                client.duel_ended_exit_duel()
                time.sleep(2)
                consecutive_failures = 0
                continue

            # Check if it's my turn
            if not client.is_my_turn():
                logger.debug("Opponent's turn. Setting confirmation to ON and canceling prompts...")
                client.cancel_activation_prompts()
                client.set_activation_confirmation(enums.ActivateConfirmMode.On)
                time.sleep(2)
                consecutive_failures = 0
                continue

            # It's our turn
            phase = client.get_current_phase()
            logger.info("Current Phase: %s", phase.name)

            if phase == enums.Phase.Draw:
                client.handle_draw_phase()
                time.sleep(1)
                consecutive_failures = 0
                continue

            # Format the state
            board_state = client.get_board_state()
            text_state = format_board_state_to_text(client, board_state)
            
            logger.info("\n--- Current Board State ---\n%s\n---------------------------", text_state)

            # Load prompts
            system_prompt = load_prompt_file("system.txt", DEFAULT_SYSTEM_PROMPT)
            examples_prompt = load_prompt_file("examples.txt", "")

            # Query LLM
            try:
                response_text = query_llm(system_prompt, examples_prompt, text_state)
                decision = clean_and_parse_json(response_text)
            except Exception as llm_err:
                logger.error("LLM query or parse failed: %s", llm_err)
                time.sleep(2)
                continue

            # Show thought process
            logger.info("[LLM Thought]: %s", decision.get("thought", "No thought provided."))
            action = decision.get("action", "WAIT")
            arguments = decision.get("arguments", {})

            # Execute
            try:
                execute_action(client, action, arguments)
                consecutive_failures = 0
                time.sleep(1.5)
            except Exception as exec_err:
                consecutive_failures += 1
                logger.error("Failed to execute action %s (%s): %s (Consecutive failures: %d)",
                             action, arguments, exec_err, consecutive_failures)
                
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning("Reached maximum consecutive failures. Forcing phase to End Turn.")
                    try:
                        client.move_phase(enums.Phase.End)
                    except Exception:
                        pass
                    consecutive_failures = 0
                time.sleep(2)

        except KeyboardInterrupt:
            logger.info("LLM Duel Bot stopped by user.")
            break
        except Exception as e:
            logger.error("LLM Duel Bot error in main loop: %s", e)
            time.sleep(3)
