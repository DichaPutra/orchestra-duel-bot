"""
Self Burn Bot — contoh bot paling simpel.
Pakai deck Self Burn (Chain Energy, Into the Void, dll).
Cuma activate card dari hand, gak perlu kombo kompleks.
"""
import logging
import time

from jduel_bot.jduel_bot_client import JDuelBotClient
from jduel_bot import jduel_bot_enums as enums

logger = logging.getLogger("orchestra.bot.self_burn")

# Kartu yang didukung bot ini (Self Burn deck)
SELF_BURN_CARDS = [
    "Chain Energy", "Cybernetic Fusion Support",
    "Toon Table of Contents", "Upstart Goblin",
    "Into the Void", "Pot of Desires",
    "Contract with Don Thousand", "Soul Levy",
    "Chain Strike", "Time-Tearing Morganite",
]


def run():
    """Main loop Self Burn bot."""
    client = JDuelBotClient("tcp://127.0.0.1:5555")
    logger.info("Self Burn bot started")

    # Tunggu server siap
    time.sleep(2)

    while True:
        try:
            # Cek duel
            if not client.is_dueling():
                logger.info("Waiting for duel...")
                time.sleep(3)
                continue

            if client.is_duel_ended():
                logger.info("Duel ended, exiting...")
                client.duel_ended_exit_duel()
                time.sleep(2)
                continue

            # Cek giliran
            if not client.is_my_turn():
                # Giliran lawan — cancel prompt, set activation ON
                client.cancel_activation_prompts()
                client.set_activation_confirmation(
                    enums.ActivateConfirmMode.On)
                time.sleep(2)
                continue

            # Giliran kita
            phase = client.get_current_phase()
            logger.info("Phase: %s", phase.name)

            if phase == enums.Phase.Draw:
                client.handle_draw_phase()
                time.sleep(1)

            elif phase == enums.Phase.Main1:
                board = client.get_board_state()
                hand = board.player_card_states[enums.Player.Myself].hand

                # Activate self-burn cards dari hand
                activated = False
                for i, card in enumerate(hand):
                    if card.name in SELF_BURN_CARDS:
                        logger.info("Activating %s from hand index %d",
                                    card.name, i)
                        try:
                            client.activate_spell_or_trap_from_hand(
                                i, enums.CardPosition.MagicC)
                            activated = True
                            time.sleep(1.5)
                        except Exception as e:
                            logger.warning("Failed to activate %s: %s",
                                           card.name, e)

                if not activated:
                    logger.info("No burn cards to activate, ending turn")
                    client.move_phase(enums.Phase.End)

            elif phase == enums.Phase.Battle:
                # Self Burn — skip battle
                client.move_phase(enums.Phase.End)

            elif phase == enums.Phase.Main2:
                client.move_phase(enums.Phase.End)

            elif phase == enums.Phase.End:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Bot stopped")
            break
        except Exception as e:
            logger.error("Bot error: %s", e)
            time.sleep(3)
