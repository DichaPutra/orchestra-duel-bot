from __future__ import annotations  # Lazily evaluate annotations (to avoid double quotes)

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from enum import IntFlag
from typing import cast, Any

spell_card = "Spell Card"
trap_card = "Trap Card"
effect_monster = "Effect Monster"
tuner_monster = "Tuner Monster"
quick_play = "Quick-Play"


@dataclass
class Coordinates:
    """
    Coordinates definition for simulating clicks
    """
    x: int
    y: int

    def __str__(self) -> str:
        """
        Returns coordinates in the format 'XxY', e.g. '1280x720'
        """
        return f"{self.x}x{self.y}"


@dataclass
class CardSelection:
    card_name: str | None = None
    card_index: int | None = None

    def __init__(self, card_name: str = None, card_index: int = None):
        if card_name is None and card_index is None:
            raise ValueError("Either the card name or card index must be provided")

        self.card_name = card_name
        self.card_index = card_index


class DuelStep(IntEnum):
    InitLoadRes = 0
    WaitLoadRes = 1
    InitializeProcess = 2
    FinishInitialize = 3
    WaitConnecting = 4
    InitEngine = 5
    InitSound = 6
    WaitSound = 7
    InitLoadSound = 8
    WaitLoadSound = 9
    WaitGameObjectInit = 10
    PrepareProcess = 11
    FinishPrepare = 12
    WaitCameraWork = 13
    ShowUpDuel = 14
    WaitShowUp = 15
    ExecDuel = 16
    EndDuel = 17
    WaitEndNetwork = 18
    DuelEnd = 19
    InitTerm = 20
    WaitEndViewClose = 21
    WaitTerm = 22
    End = 23
    WaitDestroy = 24
    ConnectingError = 25
    Beginning = 26
    InitSequenceStart = 0
    InitSequenceEnd = 12


class DuelLogViewType(IntEnum):
    Noop = -1
    Null = 0
    DuelStart = 1
    DuelEnd = 2
    WaitFrame = 3
    WaitInput = 4
    PhaseChange = 5
    TurnChange = 6
    FieldChange = 7
    CursorSet = 8
    BgmUpdate = 9
    BattleInit = 10
    BattleSelect = 11
    BattleAttack = 12
    BattleRun = 13
    BattleEnd = 14
    LifeSet = 15
    LifeDamage = 16
    LifeReset = 17
    HandShuffle = 18
    HandShow = 19
    HandOpen = 20
    DeckShuffle = 21
    DeckReset = 22
    DeckFlipTop = 23
    GraveTop = 24
    CardLockon = 25
    CardMove = 26
    CardSwap = 27
    CardFlipTurn = 28
    CardCheat = 29
    CardSet = 30
    CardVanish = 31
    CardBreak = 32
    CardExplosion = 33
    CardExclude = 34
    CardHappen = 35
    CardDisable = 36
    CardEquip = 37
    CardIncTurn = 38
    CardUpdate = 39
    ManaSet = 40
    MonstDeathTurn = 41
    MonstShuffle = 42
    TributeSet = 43
    TributeReset = 44
    TributeRun = 45
    MaterialSet = 46
    MaterialReset = 47
    MaterialRun = 48
    TuningSet = 49
    TuningReset = 50
    TuningRun = 51
    ChainSet = 52
    ChainRun = 53
    RunSurrender = 54
    RunDialog = 55
    RunList = 56
    RunSummon = 57
    RunSpSummon = 58
    RunFusion = 59
    RunDetail = 60
    RunCoin = 61
    RunDice = 62
    RunYujyo = 63
    RunSpecialWin = 64
    RunVija = 65
    RunExtra = 66
    RunCommand = 67
    CutinDraw = 68
    CutinSummon = 69
    CutinFusion = 70
    CutinChain = 71
    CutinActivate = 72
    CutinSet = 73
    CutinReverse = 74
    CutinTurn = 75
    CutinFlip = 76
    CutinTurnEnd = 77
    CutinDamage = 78
    CutinBreak = 79
    CpuThinking = 80
    HandRundom = 81
    OverlaySet = 82
    OverlayReset = 83
    OverlayRun = 84
    CutinSuccess = 85
    ChainEnd = 86
    LinkSet = 87
    LinkReset = 88
    LinkRun = 89
    RunJanken = 90
    CutinCoinDice = 91
    ChainStep = 92
    RunSpecialefx = 93


class DialogButtonType(Enum):
    Middle = 0
    Right = 1


class ExtraDeckMonsterType(Enum):
    Synchro = 0
    Xyz = 1
    Link = 2


class Player(Enum):
    Myself = 0
    Opponent = 1


class DeckType(Enum):
    Main = 0
    Extra = 1


class CardTurn(Enum):
    Invalid = -1
    Attack = 0
    Defense = 1


class CardFace(Enum):
    Invalid = -1
    FaceUp = 0
    FaceDown = 1


class CommandBit(IntFlag):
    Invalid = -1
    Attack = 1
    Look = 2
    SummonSp = 4
    Action = 8
    Summon = 16
    Reverse = 32
    SetMonst = 64
    Set = 128
    Pendulum = 256
    TurnAtk = 512
    TurnDef = 1024
    Surrender = 2048
    Decide = 4096
    Draw = 8192


@dataclass
class ChainDataItem:
    card_name: str
    position: CardPosition
    player: Player

    @staticmethod
    def from_dict(data: dict) -> ChainDataItem:
        return ChainDataItem(card_name=data["card_name"],
                             position=CardPosition(data["position"]),
                             player=Player(data["player"]))


class CardPosition(IntEnum):
    Invalid = -1
    Monster = 0
    MonsterLL = 0
    MonsterL = 1
    MonsterC = 2
    MonsterR = 3
    MonsterRR = 4
    MonsterMEnd = 4
    ExLMonster = 5
    ExRMonster = 6
    MonsterEnd = 6
    Magic = 7
    MagicLL = 7
    MagicL = 8
    MagicC = 9
    MagicR = 10
    MagicRR = 11
    MagicEnd = 11
    PendulumLeft = 7
    PendulumRight = 11
    Field = 12
    Hand = 13
    Extra = 14
    Deck = 15
    Grave = 16
    Exclude = 17
    Select = 18
    Num = 18


class CommandType(IntEnum):
    Attack = 0
    Look = 1
    SummonSp = 2
    Action = 3
    Summon = 4
    Reverse = 5
    SetMonst = 6
    Set = 7
    Pendulum = 8
    TurnAtk = 9
    TurnDef = 10
    Surrender = 11
    Decide = 12
    Draw = 13


class ActivateConfirmMode(IntEnum):
    Default = 0
    Off = 1
    On = 2


class Phase(IntEnum):
    Draw = 0
    Standby = 1
    Main1 = 2
    Battle = 3
    Main2 = 4
    End = 5
    Null = 7


class CardRarity(IntEnum):
    Invalid = -1
    Common = 0
    Rare = 1
    SuperRare = 2
    UltraRare = 3


@dataclass
class DuelCard:
    id: int
    unique_id: int
    rarity: CardRarity
    name: str
    race: str
    level: int
    attribute: str
    atk: int
    defense: int
    turn: CardTurn
    type: str
    typeline: set[str]
    description: str
    image_url: str
    archetype: str
    original_atk: int
    original_def: int
    face: CardFace
    command_bits: list[CommandBit]
    position: CardPosition

    @staticmethod
    def from_dict(data: dict[str, Any]) -> 'DuelCard':
        def safe_enum(enum_class, value: Any):
            if value is None:
                return enum_class.Invalid
            try:
                return enum_class(value)
            except (ValueError, TypeError):
                return enum_class.Invalid

        # Helper to get or default
        def get_int(key: str, default: int = 0) -> int:
            val = data.get(key)
            if val is None:
                return default
            return cast(int, val)

        def get_str(key: str, default: str = "") -> str:
            val = data.get(key)
            if val is None:
                return default
            return cast(str, val)

        # Get typeline as set[str], default empty set
        typeline_raw = cast(list, data.get("typeline"))
        typeline: set[str] = set(typeline_raw) if typeline_raw is not None else set()

        return DuelCard(
            id=get_int("id"),
            unique_id=get_int("unique_id"),
            rarity=safe_enum(CardRarity, data.get("rarity")),
            name=get_str("name"),
            race=get_str("race"),
            level=get_int("level"),
            attribute=get_str("attribute"),
            atk=get_int("atk"),
            defense=get_int("defense"),
            turn=safe_enum(CardTurn, data.get("turn")),
            type=get_str("type"),
            typeline=typeline,
            description=get_str("description"),
            image_url=get_str("image_url"),
            archetype=get_str("archetype"),
            original_atk=get_int("original_atk"),
            original_def=get_int("original_def"),
            face=safe_enum(CardFace, data.get("face")),
            command_bits=[safe_enum(CommandBit, bit) for bit in data.get("command_bits", [])],
            position=safe_enum(CardPosition, data.get("position"))
        )

    def can_be_activated(self):
        """
        Whether the card effect can be activated, this can be used for spells, traps and monsters.
        :return: If the card's effect can be activated (e.g. if the card glows in yellow)
        """
        return CommandBit.Action in self.command_bits

    def can_be_set(self):
        """
        This method can be used to check if a spell or trap can be set
        or if a monster can be set.
        :return: Whether the card can be set
        """
        # Setting spells or traps
        if self.type == spell_card or self.type == trap_card:
            return CommandBit.Set in self.command_bits

        # Setting monsters
        return CommandBit.SetMonst in self.command_bits

    def can_attack(self):
        """
        Whether the card (monster) can declare an attack
        :return: If an attack can be declared
        """
        return CommandBit.Attack in self.command_bits

    def can_be_special_summoned(self):
        """
        Whether the card (monster) can be special summoned.
        :return: If the card can be special summoned
        """
        return CommandBit.SummonSp in self.command_bits

    def can_be_normal_summoned(self):
        """
        Whether the card (monster) can be normal summoned.
        :return: If the card can be normal summoned
        """
        return CommandBit.Summon in self.command_bits

    def can_be_flip_summoned(self):
        """
        Whether the card (monster) can be flip summoned.
        :return: If the card can be flip summoned
        """
        return CommandBit.Reverse in self.command_bits

    def can_be_targeted(self):
        """
        Whether the card can be targeted.
        :return: If the card can be targeted
        """
        return CommandBit.Decide in self.command_bits

    def can_be_switched_to_atk(self):
        """
        Whether the card (monster) can be switched from DEF to ATK.
        :return: If the card can be switched to ATK
        """
        return CommandBit.TurnAtk in self.command_bits

    def can_be_switched_to_def(self):
        """
        Whether the card (monster) can be switched from ATK to DEF.
        :return: If the card can be switched to DEF
        """
        return CommandBit.TurnDef in self.command_bits


@dataclass
class PlayerCardState:
    hand: list[DuelCard]
    spells_and_traps: list[DuelCard | None]
    field_spell: DuelCard | None
    main_deck: list[DuelCard | None]
    extra_deck: list[DuelCard | None]
    graveyard: list[DuelCard | None]
    banished: list[DuelCard | None]
    monsters: list[DuelCard | None]
    xyz_materials: list[list[DuelCard | None]]

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PlayerCardState:
        def convert_list(card_list: Any) -> list[DuelCard | None]:
            if not isinstance(card_list, list):
                return []
            return [
                DuelCard.from_dict(card) if isinstance(card, dict) else None
                for card in card_list
            ]

        def convert_nested_list(nested_list: Any) -> list[list[DuelCard | None]]:
            if not isinstance(nested_list, list):
                return []
            return [convert_list(group) for group in nested_list]

        hand_raw = cast(list, data.get("hand", []))
        hand_cards = [DuelCard.from_dict(card) for card in hand_raw if card is not None]

        return PlayerCardState(
            hand=hand_cards,
            spells_and_traps=convert_list(data.get("spells_and_traps", [])),
            field_spell=DuelCard.from_dict(data["field_spell"]) if data.get("field_spell") else None,
            main_deck=convert_list(data.get("main_deck", [])),
            extra_deck=convert_list(data.get("extra_deck", [])),
            graveyard=convert_list(data.get("graveyard", [])),
            banished=convert_list(data.get("banished", [])),
            monsters=convert_list(data.get("monsters", [])),
            xyz_materials=convert_nested_list(data.get("xyz_materials", []))
        )


@dataclass
class DuelCardState:
    player_card_states: dict[Player, PlayerCardState] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict) -> DuelCardState:
        return DuelCardState(
            player_card_states={
                Player(int(key)): PlayerCardState.from_dict(value)
                for key, value in data.items()
            }
        )
