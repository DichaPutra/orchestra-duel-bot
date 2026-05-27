import abc
# noinspection PyProtectedMember
from loguru._logger import Logger

from jduel_bot.jduel_bot_client import *
from jduel_bot.jduel_bot_enums import *


# TODO Implement tracking win/loss statistics
class JDuelBotHandler(abc.ABC):
    """
    Abstract base class for a Duel Bot that handles the main duel loop.
    Subclasses should implement the phase handlers.
    """

    def __init__(self, duel_bot_client: JDuelBotClient, logger: Logger):
        self.duel_bot_client = duel_bot_client
        self.logger = logger

    def run(self):
        window_resolution = self.duel_bot_client.get_window_resolution()
        if window_resolution != supported_game_resolution:
            raise NotImplementedError("Unsupported resolution: " + str(window_resolution))

        """
        Main duel loop.
        Handles generic flow and delegates to subclass-defined phase handlers.
        """
        self.logger.info("Duel bot started...")

        while True:
            try:
                if not self.duel_bot_client.is_dueling():
                    self.while_not_dueling()
                    self.logger.info("We're not dueling...")
                    time.sleep(1)
                    continue

                if self.duel_bot_client.is_duel_ended():
                    self.logger.info("Duel ended, exiting Duel...")
                    self.duel_bot_client.duel_ended_exit_duel()
                    time.sleep(1)
                    continue

                phase = self.duel_bot_client.get_current_phase()
                self.logger.info(f"Current phase: {phase.name}")

                if self.duel_bot_client.is_my_turn():
                    self._handle_my_turn(phase)
                else:
                    self.handle_opponents_turn()

            except ActionTakenException:
                # Used as control flow signal; just retry the loop
                continue
            except Exception as exception:
                self.logger.exception(f"Unexpected error in duel loop: {exception}")

            self.logger.info("Sleeping...")
            time.sleep(1)

    # --- Internal ---
    def _handle_my_turn(self, phase):
        """
        Dispatch method for my turn phases.
        """
        if phase == Phase.Draw:
            self.handle_my_draw_phase()
        elif phase == Phase.Standby:
            self.handle_my_standby_phase()
        elif phase == Phase.Main1:
            self.handle_my_main_phase_1()
        elif phase == Phase.Battle:
            self.handle_my_battle_phase()
        elif phase == Phase.Main2:
            self.handle_my_main_phase_2()
        elif phase == Phase.End:
            self.handle_my_end_phase()

    def handle_my_draw_phase(self):
        self.logger.info("Handling draw phase...")
        self.duel_bot_client.handle_draw_phase()
        if self.duel_bot_client.cancel_activation_prompts():
            self.logger.info("Cancelling activation prompts...")

    def handle_my_standby_phase(self):
        self.logger.info("Handling standby phase...")
        if self.duel_bot_client.cancel_activation_prompts():
            self.logger.info("Cancelling activation prompts...")

    def handle_my_main_phase_2(self):
        if self.duel_bot_client.cancel_activation_prompts():
            self.logger.info("Cancelling activation prompts...")
        self.logger.info("Ending turn...")
        self.duel_bot_client.move_phase(Phase.End)

    def handle_my_end_phase(self):
        self.duel_bot_client.cancel_activation_prompts()
        # Keep discarding until we only have 6 cards in hand according to game mechanics
        while self.duel_bot_client.is_discard_ready() and self.duel_bot_client.get_hand_size(Player.Myself) >= 7:
            self.duel_bot_client.discard_leftmost_card()

    def handle_my_main_phase_1(self):
        self.duel_bot_client.cancel_activation_prompts()
        self.duel_bot_client.move_phase(Phase.Battle)

    def handle_my_battle_phase(self):
        self.duel_bot_client.cancel_activation_prompts()
        self.duel_bot_client.move_phase(Phase.Main2)

    def handle_opponents_turn(self):
        self.duel_bot_client.cancel_activation_prompts()
        self.duel_bot_client.handle_unexpected_prompts()

    def while_not_dueling(self):
        """
        Executes code when there's no duel going on (useful for clearing/resetting things)
        """
        pass
