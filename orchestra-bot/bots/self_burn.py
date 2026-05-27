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
                hand_size = len(hand)

                # Coba aktifkan kartu satu per satu secara blind (karena memory-only)
                activated = False
                for i in range(hand_size):
                    logger.info("Attempting to activate hand index %d", i)
                    try:
                        client.activate_spell_or_trap_from_hand(
                            i, enums.CardPosition.MagicC)
                        time.sleep(1.5)

                        # Cek apakah hand count berubah
                        new_board = client.get_board_state()
                        new_hand_size = len(new_board.player_card_states[enums.Player.Myself].hand)
                        if new_hand_size < hand_size:
                            logger.info("Card successfully activated! Hand size decreased from %d to %d", hand_size, new_hand_size)
                            activated = True
                            break # Break out of loop to refresh board state and restart
                    except Exception as e:
                        logger.warning("Failed to activate hand index %d: %s", i, e)

                if not activated:
                    logger.info("No more cards can be activated, ending turn")
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
