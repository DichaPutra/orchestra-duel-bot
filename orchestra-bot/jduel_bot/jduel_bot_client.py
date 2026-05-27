import json
import math
import threading
import time
from collections.abc import Callable
from dataclasses import asdict

import zmq
from loguru import logger

from jduel_bot.jduel_bot_enums import *

y_json_key = "y"
x_json_key = "x"
card_turn_json_key = "cardTurn"
index_json_key = "index"
player_json_key = "player"
position_json_key = "position"
return_value_json_key = "returnValue"

# Create a global lock since API functions
# cannot be executed from multiple threads or class instances at once
_global_duel_bot_api_lock = threading.Lock()

base_socket_connection = "tcp://127.0.0.1:"
master_duel_connection_address = "%s5555" % base_socket_connection
duel_links_connection_address = "%s5554" % base_socket_connection

supported_game_resolution = Coordinates(1280, 720)


def _command_mask_to_list(command_mask: int) -> list[CommandBit]:
    """
    Convert an integer command mask into a list of CommandBit enum members
    """
    mask = CommandBit(command_mask)
    return [bit for bit in CommandBit if bit in mask]


def _receive_response_json(response_string: str):
    """Parse and validate JSON response from server."""
    response_json = json.loads(response_string)
    error_message = response_json.get("errorMessage", "")
    if error_message:
        raise RuntimeError(f"Duel bot API error: {error_message}")
    return response_json


class JDuelBotClient:
    """
    A class used to implement duel bot clients for Master Duel and/or Duel Links
    """

    def __init__(self,
                 address: str,
                 timeout_milliseconds: int = 1000,
                 maximum_retry_count: int = 1):
        # Create context and socket only once
        self.address = address
        self.timeout_milliseconds = timeout_milliseconds
        self.maximum_retry_count = maximum_retry_count
        self.context = zmq.Context()
        self.socket = None
        self._connect()

    def _connect(self):
        """Create or recreate the ZMQ socket connection."""
        if self.socket:
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.close()
        self.socket = self.context.socket(zmq.REQ)
        # Set socket timeouts
        # TODO Not when debugging
        # self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)  # Receive timeout (ms)
        # self.socket.setsockopt(zmq.SNDTIMEO, timeout_ms)  # Send timeout (optional but safe)
        self.socket.connect(self.address)
        logger.info(f"[ZMQ] Connected to {self.address}...")

    def send_unknown_command(self):
        """
        Sends an unknown command to trigger an error (for testing)
        """
        self._send_request("unknownCommand")

    def _safe_send_and_receive(self, request_json: str) -> str | None:
        """Send and receive with reconnect retry."""
        for attempt in range(self.maximum_retry_count + 1):
            try:
                self.socket.send_string(request_json)
                response_string = self.socket.recv_string()
                return response_string
            except (zmq.error.Again, zmq.error.ZMQError) as error:
                logger.error(f"[ZMQ] Communication error: {error}. Attempt {attempt + 1}/{self.maximum_retry_count}")
                self._connect()
                if attempt < self.maximum_retry_count:
                    time.sleep(0.5 * (attempt + 1))  # exponential-ish backoff
                    continue
                else:
                    raise ConnectionError(f"Failed to communicate with server after {self.maximum_retry_count} retries.") \
                        from error

        return None

    def _send_request(self, command: str, arguments: dict = None) -> dict:
        """Send a command + arguments as JSON and handle reconnection automatically."""
        if arguments is None:
            arguments = {}

        # Convert enums to values
        for key, value in arguments.items():
            if isinstance(value, Enum):
                arguments[key] = value.value

        # Build request
        request_dict = {"command": command}
        if arguments:
            # noinspection PyTypeChecker
            request_dict["arguments"] = arguments

        request_json = json.dumps(request_dict)

        with _global_duel_bot_api_lock:
            response_string = self._safe_send_and_receive(request_json)
            if response_string is None:
                raise Exception("Failed to send and receive request JSON")
            return _receive_response_json(response_string)

    def is_dueling(self) -> bool:
        """
        Checks whether the player is currently dueling
        :return: Whether the player is dueling
        """
        response = self._send_request("isDueling")
        return bool(response.get(return_value_json_key))

    def is_inputting(self) -> bool:
        """
        Checks whether the player is currently required to provide input in a duel
        :return: Whether the player need to make a move
        """
        response = self._send_request("isInputting")
        return bool(response.get(return_value_json_key))

    def draw_for_turn(self) -> None:
        """
        Clicks the middle of the screen to draw (should be called during your draw phase).
        Requires the game to be in 1280x720 resolution.
        """
        coordinates = Coordinates(640, 360)
        self.simulate_click(coordinates)

    def duel_ended_exit_duel(self) -> None:
        """
        Clicks the bottom OK button to exit the Duel.
        Requires the game to be in 1280x720 resolution.
        """
        coordinates = Coordinates(680, 677)
        self.simulate_click(coordinates)

    def is_online(self) -> bool:
        """
        Checks whether the player is in an online Duel
        :return: Whether the player is online
        """
        response = self._send_request("isOnline")
        return bool(response.get(return_value_json_key))

    def is_duel_ended(self) -> bool:
        """
        Checks whether the duel has ended
        :return: Whether the duel is still going
        """
        response = self._send_request("isDuelEnded")
        return bool(response.get(return_value_json_key))

    def is_discard_ready(self) -> bool:
        """
        Checks whether the player is ready to discard (during the end phase)
        :return: Whether the player can discard cards right now
        """
        response = self._send_request("isDiscardReady")
        return bool(response.get(return_value_json_key))

    def discard_leftmost_card(self) -> None:
        """
        Discards the leftmost card in your hand (for use during the end phase).
        Requires a game resolution of 1280x720.
        """
        self._send_request("discardLeftmostCard")

    def set_duel_step(self, duel_step: DuelStep) -> None:
        """
        Sets the duel step in the current duel.
        Useful for e.g. exiting the duel.
        :param duel_step: The duel step to set.
        """
        self._send_request("setDuelStep", arguments={"duelStep": duel_step})

    def is_my_turn(self) -> bool:
        """
        Checks whether it's currently my turn
        :return: Whether it's my turn
        """
        response = self._send_request("isMyTurn")
        return bool(response.get(return_value_json_key))

    def get_turn_number(self) -> int:
        """
        Gets the current turn number
        :return: The turn number
        """
        response = self._send_request("getTurnNumber")
        return_value = response.get(return_value_json_key)
        return cast(int, return_value)

    def get_current_phase(self) -> Phase:
        """
        Gets the current Duel phase
        :return: The Duel phase
        """
        response = self._send_request("getCurrentPhase")
        return Phase(response.get(return_value_json_key))

    def get_board_state(self) -> DuelCardState:
        response = self._send_request("getBoardState")
        response_value = response.get(return_value_json_key)
        raw_state = cast(dict, response_value)
        return DuelCardState.from_dict(raw_state)

    def wait_for_input_enabled(self):
        """
        A useful utility function that will stall until the player has input again (e.g. when the player can make a move)
         - Prevents sending commands too quickly (which causes desyncs with scripts?)
        - Ensures animations finish before next action
         When NOT to use:
        - Before actions (game is already waiting)
        - After get_board_state() or other query functions (no animation)
        - After is_my_turn() or similar checks (instant return)
        Common pattern:
        ```python
        duel_bot_client.execute_command(Player.Myself, CardPosition.Hand, 0, CommandType.Action)
        duel_bot_client.wait_for_input_enabled()  # Wait for activation to finish
        # Now safe to do next action
        ```
        """
        self._send_request("waitForInputEnabled")

    def simulate_click(self, coordinates: Coordinates) -> None:
        """
        Simulates a mouse click at the specified in-game coordinates
        :param coordinates: The coordinates to simulate a click at
        """
        self._send_request("simulateClick", {x_json_key: coordinates.x, y_json_key: coordinates.y})

    def get_lp(self, player: Player) -> int:
        """
        Gets the LP of a player
        :param player: The player to get the LP from
        :return: The LP
        """
        response = self._send_request("getLP", {player_json_key: player})
        return_value = response.get(return_value_json_key)
        return cast(int, return_value)

    def move_phase(self, phase: Phase) -> None:
        """
        Moves between Duel phases
        :param phase: The phase to move to
        """
        self._send_request("movePhase", {"phase": phase})
        self.wait_for_input_enabled()

    def activate_spell_or_trap_from_hand(self, index: int, position: CardPosition) -> None:
        """
        Forces the player to activate a spell card
        :param index: The hand index of the spell card to activate
        :param position: The spell/trap card position to activate the card in
        """
        self.execute_command(Player.Myself, CardPosition.Hand, index, CommandType.Action)
        self.wait_for_input_enabled()
        self.execute_command(Player.Myself, position, 0, CommandType.Decide)
        self.wait_for_input_enabled()

    def set_spell_or_trap_from_hand(self, index: int, position: CardPosition) -> None:
        """
        Makes the player set a spell or trap card
        :param index: The hand index of the spell or trap card to set
        :param position: The spell/trap card position to set the card in
        """
        self.execute_command(Player.Myself, CardPosition.Hand, index, CommandType.Set)
        self.wait_for_input_enabled()
        self.execute_command(Player.Myself, position, 0, CommandType.Decide)
        self.wait_for_input_enabled()

    def activate_spell_or_trap_from_field(self, position: CardPosition) -> None:
        """
            Makes the player activate a set spell or trap card
            :param position: The spell/trap card position to activate
        """
        self.execute_command(Player.Myself, position, 0, CommandType.Action)
        self.wait_for_input_enabled()

    def special_summon_monster_from_hand(self, index: int, position: CardPosition,
                                         timeout_seconds: int = 5,
                                         card_turn: CardTurn = CardTurn.Attack) -> None:
        """
        Makes the player special summon a monster
        :param timeout_seconds: The timeout for the summon operation before it fails
        :param index: The hand index of the monster to summon
        :param position: The monster card zone to summon the card in
        :param card_turn: The turn to summon the card in
        """
        arguments = {index_json_key: index, position_json_key: position,
                     "timeoutSeconds": timeout_seconds, card_turn_json_key: card_turn}
        self._send_request("specialSummonFromHand", arguments)

    def confirm_card_turn(self, card_turn: CardTurn) -> None:
        """
        Confirms the card turn when summoning by clicking.
        Only works under 1280x720 game resolution.
        :param card_turn: The card turn to confirm
        """
        arguments = {card_turn_json_key: card_turn}
        self._send_request("confirmCardTurn", arguments)

    def normal_summon_monster(self, index: int, position: CardPosition) -> None:
        """
        Makes the player normal summon a monster
        :param index: The hand index of the monster to summon
        :param position: The monster card zone to summon the card in
        """
        self.execute_command(Player.Myself, CardPosition.Hand, index, CommandType.Summon)
        self.wait_for_input_enabled()
        self.execute_command(Player.Myself, position, 0, CommandType.Decide)
        self.wait_for_input_enabled()

    def get_hand_size(self, player: Player) -> int:
        """
        Gets the hand size of a player
        :param player: The player to get the hand size from
        :return: The hand size
        """
        response = self._send_request("getCardInHand", {player_json_key: player})
        response_value = response.get(return_value_json_key)
        return cast(int, response_value)

    def get_command_mask(self, player: Player, position: CardPosition, index: int) -> list[CommandBit]:
        """
        Returns which types of commands can be performed on that card.
        :param player: The player
        :param position: The card position
        :param index: The card index
        :return: The command mask (an int value consisting of CommandBit flags)
        """
        arguments = {player_json_key: player, position_json_key: position, index_json_key: index}
        response = self._send_request("comGetCommandMask", arguments)
        return_value = response.get(return_value_json_key)
        command_mask = cast(int, return_value)
        return _command_mask_to_list(command_mask)

    def get_card_id(self, player: Player, position: CardPosition, index: int) -> int:
        """
        Returns the card id at this location.
        :param player: The player
        :param position: The card position
        :param index: The card index
        :return: The card ID ("KONAMI ID")
        """
        arguments = {player_json_key: player, position_json_key: position, index_json_key: index}
        response = self._send_request("getCardID", arguments)
        return_value = response.get(return_value_json_key)
        return cast(int, return_value)

    def get_card_turn(self, player: Player, position: CardPosition, index: int) -> CardTurn:
        """
        Returns the card position at this location.
        :param player: The player
        :param position: The card position
        :param index: The card index
        :return: The card turn
        """
        arguments = {player_json_key: player, position_json_key: position, index_json_key: index}
        response = self._send_request("getCardTurn", arguments)
        return CardTurn(response.get(return_value_json_key))

    def get_card_face(self, player: Player, position: CardPosition, index: int) -> CardFace:
        """
        Returns the card face at this location.
        :param player: The player
        :param position: The card position
        :param index: The card index
        :return: The card face
        """
        arguments = {player_json_key: player, position_json_key: position, index_json_key: index}
        response = self._send_request("getCardFace", arguments)
        return CardFace(response.get(return_value_json_key))

    def set_activation_confirmation(self, activation_confirmation: ActivateConfirmMode) -> bool:
        """
        Sets the activation confirmation mode
        :param activation_confirmation: The activation confirmation mode
        :return: Whether the operation was successful
        """
        arguments = {"activateConfirmMode": activation_confirmation}
        response = self._send_request("setActivationConfirmation", arguments)
        return bool(response.get(return_value_json_key))

    def get_dialog_card_list(self) -> list[str]:
        """
        Gets the list of card names currently displayed in any dialog/prompt. (mostly...)
        
        What this returns:
        - Card selection dialogs: List of selectable card names
        - Chain prompts: Card names that can be chained (may include opponent's cards)
        - Empty list if no dialog is present
        
        CRITICAL - YES/NO dialogs are NOT supported:
        - YES/NO prompts (middle of screen) DO NOT work with this API (and more when it comes to the middle of the screen?)
        - For example: "Activate effect?" prompts
        - For YES/NO dialogs, must use simulate_click(Coordinates(734, 408)) for YES button
        - This is a known API limitation...
        - Note: handle_continue_main_phase_prompt() handles "Continue Main Phase?" specifically
        - Coordinate clicking is fragile (resolution-dependent, may break with game updates) try using as last resort
        
        IMPORTANT - Dialog context matters:
        - Search dialogs show cards from DECK/GY/HAND depending on the effect
        - Do NOT assume dialog cards are YOUR hand - check context first
        
        Common usage:
        - Check if specific card is available in selection dialog
        - Detect opponent activation (by example: chain "Ash Blossom" in dialog during opponent chain)
        - Verify card selection prompts by checking if expected card name is present
        
        Card name matching:
        - Names include exact punctuation (by example: "Ash Blossom & Joyous Spring" with &)
        - Use exact string matching or "in" checks: if "Ash Blossom" in card_name
        
        :return: List of card name strings currently shown in dialogs (empty if no dialog)
        """
        response = self._send_request("getDialogCardList")
        return_value = response.get(return_value_json_key)
        return cast(list, return_value)

    def get_window_resolution(self) -> Coordinates:
        """
        Gets the game window's resolution coordinates.
        :return: The x, y coordinate class object
        """
        response = self._send_request("getWindowResolution")
        coordinates = response.get(return_value_json_key)
        return Coordinates(coordinates[x_json_key], coordinates[y_json_key])

    def surrender_duel(self) -> None:
        """
        Surrenders the duel. Only works under 1280x720 game resolution.
        :return:
        """
        self._send_request("surrenderDuel")

    def cancel_activation_prompts(self) -> bool:
        """
        Clicks the cancel button if the player is required to provide input and presses the ESC key.
        Clicking only works properly on 1280x720 resolution.
        """
        response = self._send_request("cancelActivationPrompts")
        return bool(response.get(return_value_json_key))

    def execute_command(self, player: Player, position: CardPosition, index: int,
                        command_id: CommandType) -> None:
        """
        Executes a command during the Duel.
        :param player: The player
        :param position: The card position
        :param index: The card index
        :param command_id: The command to execute
        """
        arguments = {player_json_key: player, position_json_key: position, index_json_key: index,
                     "commandId": command_id}
        self._send_request("comDoCommand", arguments)

    def turn_defense(self, position: CardPosition) -> None:
        """
        Turns the monster to defense position
        :param position: The monster to turn
        """
        self.execute_command(Player.Myself, position, 0, CommandType.TurnDef)
        self.wait_for_input_enabled()

    def turn_attack(self, position: CardPosition) -> None:
        """
        Turns the monster to attack position
        :param position: The monster to turn
        """
        self.execute_command(Player.Myself, position, 0, CommandType.TurnAtk)
        self.wait_for_input_enabled()

    def set_monster(self, index: int, position: CardPosition) -> None:
        """
        Sets a monster from the hand
        :param index: The monster to set
        :param position: The zone to place the monster in
        """
        self.execute_command(Player.Myself, CardPosition.Hand, index, CommandType.SetMonst)
        self.wait_for_input_enabled()
        self.execute_command(Player.Myself, position, 0, CommandType.Decide)
        self.wait_for_input_enabled()

    def perform_flip_summon(self, position: CardPosition) -> None:
        """
        Flips the monster from face-down defense position to face-up attack position
        :param position: The monster to flip
        """
        self.execute_command(Player.Myself, position, 0, CommandType.Reverse)
        self.wait_for_input_enabled()

    def get_chain_data(self) -> list[ChainDataItem]:
        """
        Gets data about the current chain.

        Note that this function maybe isn't as useful as one would expect:
        The chain data is only updated when a chain link 2 is happening, otherwise it stays at 1 element at all times,
        which might be outdated, even outside of chains. Be cautious when relying on this function
        to ensure it helps for your use case.

        Once this function's functionality changes or improves regarding these shortcomings,
        this code documentation will also be updated.
        :return: The list of chain data items
        """
        response = self._send_request("getChainData")
        raw_chain_data = response.get(return_value_json_key, [])
        return [ChainDataItem.from_dict(chain_data_item) for chain_data_item in raw_chain_data]

    def get_duel_log(self) -> list[DuelLogViewType]:
        """
        Returns a list of duel log entries in the current duel so far
        :return: The list of duel log entries
        """
        response = self._send_request("getDuelLog")
        raw_duel_log_data = response.get(return_value_json_key, [])
        return [DuelLogViewType(value) for value in raw_duel_log_data]

    def target_card(self, player: Player, position: CardPosition) -> None:
        """
        Targets a card
        :param player: The player to target
        :param position: The position to target
        """
        self.execute_command(player, position, 0, CommandType.Decide)
        self.wait_for_input_enabled()

    def get_last_used_card_name(self) -> str:
        """
        Gets the card that was activated/used last.
        This is e.g. useful for handling interaction with the opponent's cards.
        :return: The name of the card
        """
        response = self._send_request("getLastUsedCardName")
        return str(response.get(return_value_json_key))

    def can_we_battle(self, board_state: DuelCardState) -> bool:
        """
        Determines if we have monsters that could theoretically attack.
        Useful for entering the battle phase or not.
        :param board_state: The current board state
        :return: Whether we can attack
        """
        monsters = board_state.player_card_states.get(Player.Myself).monsters
        turn_number = self.get_turn_number()
        return turn_number > 1 and any(monster is not None
                                       and monster.face == CardFace.FaceUp
                                       and monster.turn == CardTurn.Attack
                                       for monster in monsters)

    def activate_monster_effect_from_hand(self, index: int) -> None:
        """
        Activates a monster effect from the hand
        :param index: The card index to activate
        """
        self.execute_command(Player.Myself, CardPosition.Hand, index, CommandType.Action)
        self.wait_for_input_enabled()

    def activate_monster_effect_from_field(self, position: CardPosition) -> None:
        """
        Activates a monster effect from the field
        :param position: The position to activate
        """
        self.execute_command(Player.Myself, position, 0, CommandType.Action)
        self.wait_for_input_enabled()

    def get_monster_zone_coordinates(self, player: Player, position: CardPosition) -> Coordinates:
        """
        Gets the in-game coordinates of the monster to click on
        :param player: The player to target
        :param position: The position to use
        :return: The x, y coordinates of the monster zone
        """
        arguments = {player_json_key: player, position_json_key: position}
        response = self._send_request("getMonsterZoneCoordinates", arguments)
        return_value = response.get(return_value_json_key)
        return Coordinates(return_value[x_json_key], return_value[y_json_key])

    def print_monster_zone_coordinates(self) -> None:
        """
        Prints all monster zone coordinates for use in forcing clicks
        This function is only useful for debugging
        """
        players = [Player.Myself, Player.Opponent]
        for player in players:
            logger.info(f"Player: {player.name}")
            for name, position in CardPosition.__members__.items():
                if position < CardPosition.Monster or position > CardPosition.MonsterEnd:
                    continue
                coordinates = self.get_monster_zone_coordinates(player, position)
                logger.info(f"{name} ({position}): {coordinates}")

    def special_summon_to_opponents_side(self,
                                         index: int,
                                         tributes: list[CardPosition],
                                         card_turn: CardTurn = CardTurn.Invalid,
                                         position: CardPosition = CardPosition.Invalid) -> None:
        """
        Performs a special summon to the opponent's side.
        :param index: The hand card index to summon
        :param tributes: The monsters from opponent to tribute
        :param card_turn: The card turn to summon the monster in (e.g. ATK or DEF)
        :param position: The position at opponent to summon the card to
        """
        self.perform_tribute_summon(index, tributes, card_turn, Player.Opponent, CommandType.SummonSp, position)

    def perform_tribute_summon(self,
                               index: int,
                               tributes: list[CardPosition],
                               card_turn: CardTurn,
                               player: Player = Player.Myself,
                               summon_method: CommandType = CommandType.Summon,
                               position: CardPosition = CardPosition.Invalid) -> None:
        """
        Performs a tribute summon.
        :param index: The hand card index to summon
        :param tributes: The monsters to tribute
        :param card_turn: The card turn to summon the monster in (e.g. ATK or DEF)
        :param player: The player who summons the card to their side of the field
        :param summon_method: The summon method to use (only CommandType.Summon and CommandType.SummonSp are allowed)
        :param position: The position to summon the card to
        """
        arguments = {index_json_key: index, "tributes": tributes, card_turn_json_key: card_turn,
                     player_json_key: player, "summonMethod": summon_method, position_json_key: position}
        self._send_request("performTributeSummon", arguments)

    def declare_attack(self, position: CardPosition, target_position: CardPosition = None) -> None:
        """
        Declares an attack from a monster on another monster
        :param position: The attacking monster
        :param target_position: The attacked monster
        """
        if target_position is None:
            arguments = {position_json_key: position}
        else:
            arguments = {position_json_key: position, "targetPosition": target_position}
        self._send_request("declareAttack", arguments)

    def _select_card_from_dialog(self, card_selection: CardSelection | None = None,
                                 dialog_button_type: DialogButtonType = DialogButtonType.Middle,
                                 milliseconds_delay_between_clicks: int = 80):
        if card_selection is None:
            card_selection = CardSelection(card_index=0)
            assert card_selection is not None

        self.select_cards_from_dialog([card_selection], dialog_button_type, milliseconds_delay_between_clicks)

    def select_cards_from_dialog(self, card_selections: list[CardSelection],
                                 dialog_button_type: DialogButtonType = DialogButtonType.Middle,
                                 milliseconds_delay_between_clicks: int = 80):
        """
        Selects multiple cards from a selection dialog.
        This method only works under 1280x720 game resolution.
        :param card_selections: The card to select by card name or card index
        :param dialog_button_type: Which button to click after the card selection
        :param milliseconds_delay_between_clicks: The milliseconds delay between the 2 clicks (select the card and confirm)
        """
        arguments = {"cardSelections": [asdict(card_selection) for card_selection in card_selections],
                     "dialogButtonType": dialog_button_type.value,
                     "millisecondsDelayBetweenClicks": milliseconds_delay_between_clicks}
        self._send_request("selectCardsFromDialog", arguments)

    def select_card_from_dialog(self, card_selection: CardSelection | None = None,
                                dialog_button_type: DialogButtonType = DialogButtonType.Middle,
                                milliseconds_delay_between_clicks: int = 80) -> None:
        if card_selection is None:
            card_selection = CardSelection(card_index=0)
            assert card_selection is not None

        available_card_names = self.get_dialog_card_list()
        try:
            card_name = card_selection.card_name
            if card_name is not None:
                card_index = available_card_names.index(card_name)
            else:
                card_index = card_selection.card_index
        except ValueError:
            # logger.error(f"Karte \"{card_name}\" nicht in der Dialogliste gefunden.")
            return

        if card_index is None:
            return

        if card_index <= 6:
            # logger.info(f"Wähle Karte \"{card_name}\" über Standard-Dialog (Index: {card_index}).")
            self._select_card_from_dialog(card_selection, dialog_button_type, milliseconds_delay_between_clicks)
            return
        # logger.info(f"Karte \"{card_name}\" (Index: {card_index}) erfordert Tabellenansicht.")
        # logger.info("Öffne Tabellenansicht...")
        self.simulate_click(Coordinates(862, 469))
        self.wait_for_input_enabled()
        total_cards = len(available_card_names)
        num_rows = math.ceil(total_cards / 8)
        card_row_in_list = card_index // 8
        column_index = card_index % 8
        y = 0
        if num_rows == 1:
            if card_row_in_list == 0: y = 618

        elif num_rows == 2:
            if card_row_in_list == 0:
                y = 490
            elif card_row_in_list == 1:
                y = 618

        elif num_rows >= 3:
            if card_row_in_list == 0:
                y = 360
            elif card_row_in_list == 1:
                y = 490
            elif card_row_in_list == 2:
                y = 618
        if y == 0:
            # logger.error(
            #    f"Karten-Index {card_index} (Reihe {card_row_in_list}) außerhalb der erwarteten {num_rows} Reihen.")
            return
        x = 375 + (column_index * 75)
        final_coords = Coordinates(x, y)
        # logger.info(
        #    f"Wähle Karte über Koordinate (N={total_cards}, Reihe={card_row_in_list}, Spalte={column_index}): {final_coords.x}, {final_coords.y}")
        self.simulate_click(final_coords)
        self.wait_for_input_enabled()
        self.simulate_click(Coordinates(640, 710))

    def get_deck_size(self, player: Player, deck_type: DeckType) -> int:
        """
        Gets the deck size of the specified player and deck type.
        :param player: The player to query.
        :param deck_type: The deck type to query.
        :return: The deck size
        """
        arguments = {player_json_key: player, "deckType": deck_type}
        response = self._send_request("getDeckSize", arguments)
        return_value = response.get(return_value_json_key)
        return cast(int, return_value)

    # TODO Handle e.g. "Evenly Matched" and "Dark World Dealings"
    def handle_unexpected_prompts(self) -> None:
        """
        Handles unexpected dialogs (e.g. "My Friend Purrely", "Bingo Machine, Go!!!", "Reasoning" etc.).
        This method will only work correctly under a 1280x720 game resolution.
        """
        last_used_card_name = self.get_last_used_card_name()
        # logger.info(f"Last used card: {last_used_card_name}")

        bingo_machine_go = "Bingo Machine, Go!!!"
        my_friend_purrely = "My Friend Purrely"
        reasoning = "Reasoning"

        special_handling_cards = {bingo_machine_go, my_friend_purrely, reasoning}

        first_chain_card_name = self._get_first_chain_card_name()
        if (first_chain_card_name is not None
                and first_chain_card_name in special_handling_cards):
            last_used_card_name = first_chain_card_name

        if (last_used_card_name == bingo_machine_go
                or last_used_card_name == my_friend_purrely):
            # Choose the first card and confirm
            self.select_card_from_dialog(CardSelection(card_index=0))
        elif last_used_card_name == reasoning:
            self.simulate_click(Coordinates(640, 272))  # Choose level 1
            time.sleep(0.2)  # Delay between clicks
            self.simulate_click(Coordinates(640, 539))  # Click the OK button
            time.sleep(0.5)

    def _get_first_chain_card_name(self) -> str | None:
        # Consider overriding the last used card name if there was a chain
        chain_data_list = self.get_chain_data()
        if len(chain_data_list) == 1:
            chain_data = chain_data_list[0]

            # Ensure the card is still there before returning the card name
            board_state = self.get_board_state()
            spells_and_traps = board_state.player_card_states.get(chain_data.player).spells_and_traps
            for opponent_spell_or_trap in spells_and_traps:
                if (opponent_spell_or_trap is not None
                        and opponent_spell_or_trap.position == chain_data.position
                        and opponent_spell_or_trap.name == chain_data.card_name):
                    return chain_data.card_name

        return None

    def perform_extra_deck_summon(self, extra_deck_monster_name: str, positions: list[CardPosition]):
        arguments = {"extraDeckMonsterName": extra_deck_monster_name,
                     "positions": [int(position.value) for position in positions]}
        self._send_request("performExtraDeckSummon", arguments)

    def get_player_name(self, player: Player) -> str:
        """
        Gets the name of the specified player
        :param player: The player to query
        :return: The name of the player
        """
        arguments = {player_json_key: player}
        response = self._send_request("getPlayerName", arguments)
        return_value = response.get(return_value_json_key)
        return str(return_value)

    def click_my_monster_zone(self, position: CardPosition) -> None:
        """
        Clicks a monster zone on your side of the field
        :param position: The position to click
        """
        arguments = {position_json_key: position}
        self._send_request("clickMyMonsterZone", arguments)

    def handle_draw_phase(self) -> None:
        """
        Handles the draw phase by drawing but only on turn 2 and beyond
        """
        turn_number = self.get_turn_number()
        # Only draw when it's not the first turn
        if turn_number != 1:
            self.draw_for_turn()

    def _has_spell_or_trap(self, card_name: str, face: CardFace, player: Player) -> bool:
        """Internal helper: checks if the player has a spell/trap with the given name and face."""
        board_state = self.get_board_state()
        cards = board_state.player_card_states[player].spells_and_traps

        return any(card is not None
                   and card.name == card_name
                   and card.face == face
                   for card in cards)

    def has_face_up_spell_or_trap(self, card_name: str, player: Player = Player.Myself) -> bool:
        return self._has_spell_or_trap(card_name, CardFace.FaceUp, player)

    def has_face_down_spell_or_trap(self, card_name: str, player: Player = Player.Myself) -> bool:
        return self._has_spell_or_trap(card_name, CardFace.FaceDown, player)

    def _get_preferred_zones(self, zone_type: CardPosition) -> list[CardPosition]:
        """Return preferred zone order based on zone type and connection."""
        is_duel_links = self.address == duel_links_connection_address

        if zone_type == CardPosition.Monster:
            if is_duel_links:
                return [
                    CardPosition.MonsterC,
                    CardPosition.MonsterR,
                    CardPosition.MonsterL,
                    CardPosition.ExLMonster,
                    CardPosition.ExRMonster,
                ]
            else:
                return [
                    CardPosition.MonsterC,
                    CardPosition.MonsterR,
                    CardPosition.MonsterL,
                    CardPosition.MonsterRR,
                    CardPosition.MonsterLL,
                    CardPosition.ExLMonster,
                    CardPosition.ExRMonster,
                ]

        elif zone_type == CardPosition.Magic:
            if is_duel_links:
                return [
                    CardPosition.MagicC,
                    CardPosition.MagicR,
                    CardPosition.MagicL,
                ]
            else:
                return [
                    CardPosition.MagicC,
                    CardPosition.MagicR,
                    CardPosition.MagicL,
                    CardPosition.MagicRR,
                    CardPosition.MagicLL,
                ]

        raise ValueError(f"Unknown zone type: {zone_type}")

    def get_occupied_monster_card_zones(self, board_state: DuelCardState, amount: int) -> list[CardPosition] | None:
        monsters = board_state.player_card_states[Player.Myself].monsters
        preferred_zones = self._get_preferred_zones(CardPosition.Monster)
        return get_occupied_card_zones(monsters, CardPosition.Monster, preferred_zones, amount)

    def get_free_monster_card_zone(self, board_state: DuelCardState) -> CardPosition | None:
        monsters = board_state.player_card_states[Player.Myself].monsters
        preferred_zones = self._get_preferred_zones(CardPosition.Monster)
        return get_free_card_zone(monsters, CardPosition.Monster, preferred_zones)

    def get_free_spell_or_trap_card_zone(self, board_state: DuelCardState) -> CardPosition | None:
        spells_and_traps = board_state.player_card_states[Player.Myself].spells_and_traps
        preferred_zones = self._get_preferred_zones(CardPosition.Magic)
        return get_free_card_zone(spells_and_traps, CardPosition.Magic, preferred_zones)

    def get_opponent_occupied_monster_card_zones(self, board_state: DuelCardState, amount: int) -> list[
                                                                                                       CardPosition] | None:
        monsters = board_state.player_card_states[Player.Opponent].monsters
        preferred_zones = self._get_preferred_zones(CardPosition.Monster)
        return get_occupied_card_zones(monsters, CardPosition.Monster, preferred_zones, amount)

    def get_opponent_free_monster_card_zone(self, board_state: DuelCardState) -> CardPosition | None:
        monsters = board_state.player_card_states[Player.Opponent].monsters
        preferred_zones = self._get_preferred_zones(CardPosition.Monster)
        return get_free_card_zone(monsters, CardPosition.Monster, preferred_zones)

    def __del__(self):
        # Clean up the socket and context when the object is destroyed
        # noinspection PyBroadException
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass  # Avoid errors during interpreter shutdown


def _find_card_zones(card_slots: list[DuelCard | None],
                     base_position: CardPosition,
                     preferred_order: list[CardPosition],
                     predicate: Callable[[DuelCard | None], bool],
                     amount: int | None = None) -> list[CardPosition] | None:
    """
    Generic zone finder that can locate occupied or free card zones.

    :param card_slots: List of DuelCard or None
    :param base_position: Base CardPosition to calculate index offset
    :param preferred_order: Preferred order to check
    :param predicate: Function to test each slot (e.g. lambda slot: slot is None)
    :param amount: How many zones to return (None = return first match)
    :return: A list of matching CardPositions or None if none found
    """
    found_zones = []
    for preferred_zone in preferred_order:
        index = int(preferred_zone) - int(base_position)
        if 0 <= index < len(card_slots) and predicate(card_slots[index]):
            found_zones.append(preferred_zone)
            # Return early if we're only looking for the first one
            if amount is None or len(found_zones) == amount:
                return found_zones if amount else found_zones[0:1]
    return None if amount else None


def get_tribute_targets(monsters: list[DuelCard | None],
                        priority: Callable[[DuelCard], int],
                        amount: int) -> list[CardPosition] | None:
    """
    Gets tribute targets sorted by a priority lambda for use with e.g. Lava Golem etc.
    :param monsters: The monsters to scan (e.g. the opponent's)
    :param priority: A lambda function for specifying card priority
    :param amount: The amount of tribute targets to return
    :return: The list of card positions or none if not possible
    """
    valid_tribute_targets = [monster for monster in monsters if monster is not None]

    if len(valid_tribute_targets) < amount:
        return None

    # Sort the tributes by priority
    sorted_tributes = sorted(valid_tribute_targets, key=priority, reverse=True)

    tributes = sorted_tributes[:amount]

    # Check how many extra monster zones are in top 2
    extra_positions = {CardPosition.ExLMonster, CardPosition.ExRMonster}
    extra_monster_tributes = [monster for monster in tributes if monster.position in extra_positions]

    if len(extra_monster_tributes) == amount:
        is_empty_main_monster_zone = any(monster is not None
                                         and monster.position not in (CardPosition.ExLMonster,
                                                                      CardPosition.ExRMonster)
                                         for monster in monsters)

        if not is_empty_main_monster_zone:
            # Not allowed: pick the best non-extra monster instead of the weaker one
            non_extra_monsters = [
                monster for monster in sorted_tributes
                if monster.position not in extra_positions
            ]

            if not non_extra_monsters:
                return None  # No legal tribute combination possible

            # Replace the *weaker* of the two extra tributes
            weaker_extra = min(extra_monster_tributes, key=lambda monster: monster.atk)
            replacement = non_extra_monsters[0]  # highest ATK non-extra

            tributes.remove(weaker_extra)
            tributes.append(replacement)

    # Final tribute positions
    tribute_positions = [monster.position for monster in tributes]

    return tribute_positions


def get_occupied_card_zones(card_slots: list[DuelCard | None],
                            base_position: CardPosition,
                            preferred_order: list[CardPosition],
                            amount: int) -> list[CardPosition] | None:
    """Finds the next occupied card slot(s) from the preferred order."""
    return _find_card_zones(card_slots, base_position, preferred_order, predicate=lambda card: card is not None,
                            amount=amount)


def get_free_card_zone(card_slots: list[DuelCard | None],
                       base_position: CardPosition,
                       preferred_order: list[CardPosition]) -> CardPosition | None:
    """Finds the next empty card slot from the preferred order."""
    result = _find_card_zones(card_slots, base_position, preferred_order, predicate=lambda card: card is None)
    # _find_card_zones returns a list even for one; simplify it
    return result[0] if result else None


def move_item(item_list: list, item: Any, index: int) -> None:
    try:
        old_index = item_list.index(item)
    except ValueError:
        return  # item not in list → do nothing

    # Remove from old position
    element = item_list.pop(old_index)

    # Clamp the index to valid bounds
    if index < 0:
        index = 0
    elif index > len(item_list):
        index = len(item_list)

    # Insert at new position
    item_list.insert(index, element)


class ActionTakenException(Exception):
    """Custom exception for controlling the control flow when an action was taken by the duel bot"""
    pass


class CardActivationTracker:
    def __init__(self, duel_bot_client):
        # Maps turn number -> set of activated card names
        self.activated_cards: dict[int, set[str]] = {}
        self.duel_bot_client = duel_bot_client

    def mark_card(self, card_name: str) -> None:
        """
        Marks a card as activated this turn
        :param card_name: The card to mark as activated
        """
        turn = self.duel_bot_client.get_turn_number()
        if turn not in self.activated_cards:
            self.activated_cards[turn] = set()
        self.activated_cards[turn].add(card_name)

    def is_activated(self, card_name: str) -> bool:
        """
        Checks if this card was already activated this turn
        :param card_name: The name of the card to check
        :return: Whether this card was already activated this turn
        """
        turn = self.duel_bot_client.get_turn_number()
        return card_name in self.activated_cards.get(turn, set())

    def reset(self):
        """Clears tracking for all turns"""
        self.activated_cards.clear()
