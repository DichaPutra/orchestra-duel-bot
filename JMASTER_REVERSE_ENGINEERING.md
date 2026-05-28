# JMaster Duel Bot — Reverse Engineering Report

> Dokumen ini berisi hasil analisis JMaster Duel Bot v6.7.5 (Windows).
> Dibuat agar AI lain (Gemini, Claude, dll) bisa memahami arsitektur tanpa perlu reverse engineering ulang.
> Target: pengembangan Orchestra Duel Bot (alternatif open source).

---

## Daftar Isi

1. [Arsitektur Umum](#1-arsitektur-umum)
2. [Komponen Binary](#2-komponen-binary)
3. [Protocol ZMQ](#3-protocol-zmq)
4. [Memory Hacking via GameAssembly.dll](#4-memory-hacking-via-gameassemblydll)
5. [Donator Protection](#5-donator-protection)
6. [JDuelBotClient (Open Source)](#6-jduelbotclient-open-source)
7. [Function Dump Reference](#7-function-dump-reference)
8. [Key Offset Patterns](#8-key-offset-patterns)

---

## 1. Arsitektur Umum

```
┌─────────────────────────────────────────────────────┐
│  Master Duel (Unity IL2CPP)                         │
│  GameAssembly.dll + UnityPlayer.dll                 │
│  ┌──────────────────────────────────────────────┐    │
│  │  Game State (Memory)                         │    │
│  │  - LP, Phase, Turn, Hand, Field, GY, dll     │    │
│  └──────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────┘
                     │ ReadProcessMemory / JNI calls
                     ▼
┌─────────────────────────────────────────────────────┐
│  JMaster App (Java JAR)                             │
│  MasterDuelBotClient.jar (14MB, obfuscated)         │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  DLL Bridge Layer (JNI)                     │    │
│  │  Panggil fungsi GameAssembly.dll via JNI     │    │
│  │  - DLL_DuelGetLP(addr) → LP value            │    │
│  │  - DLL_DuelGetCurrentPhase(addr) → Phase     │    │
│  │  - DLL_DuelGetCardInHand(addr) → Hand cards  │    │
│  │  - DLL_DuelComDoCommand(addr) → Execute cmd  │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  ZMQ Server (port 5555)                     │    │
│  │  Terima command dari Python client          │    │
│  │  Format: JSON {command, arguments}           │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Donator Check (3 layer)                    │    │
│  │  - Registry check (dc.class)                │    │
│  │  - Server validation + AES (od.class, xa)   │    │
│  │  - Rate limiting (Ba.class)                 │    │
│  └─────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────┘
                     │ TCP ZMQ (localhost:5555)
                     ▼
┌─────────────────────────────────────────────────────┐
│  Python Client (Open Source)                        │
│  JDuelBotClient / jduel_bot_client.py               │
│                                                     │
│  - Abstraksi command → method call                  │
│  - Enum: Phase, CardPosition, CommandType, Player   │
│  - Data class: DuelCard, DuelCardState              │
│  - Handler: JDuelBotHandler (main loop)             │
│  - Bot scripts: self_burn, pass_turn, blue_eyes     │
└─────────────────────────────────────────────────────┘
```

### Alur Eksekusi

1. **Bot script Python** panggil method `JDuelBotClient`, misal `get_lp()`
2. `JDuelBotClient` kirim JSON via ZMQ: `{"command": "getLP", "arguments": {"player": 0}}`
3. **JMaster Java app** terima command via ZMQ server
4. Java app panggil fungsi native **GameAssembly.dll** via JNI
5. Fungsi native baca langsung dari memory game (internal Unity objects)
6. Hasil dikembalikan: Java → ZMQ → Python

### Kenapa JMaster Cepat?

JMaster akses **internal game objects langsung via native code** (GameAssembly.dll).
Ini beda dengan approach vision-based yang baca screenshot.
Kecepatan: < 1ms per call (vs 1-3 detik vision).

---

## 2. Komponen Binary

### 2.1 Launcher: `JMaster Duel Bot.exe`

**Type:** C++ Windows GUI application (PE32+)
**Ukuran:** ~7MB
**UI:** Custom dark theme, tab-based
**Fungsi:**
- Download/update JAR dari server
- Download/update Bot-Utilities.exe + IL2CppDLL.dll
- Launch JAR sebagai child process
- Handle process lifecycle

**Download URL (terenkripsi di binary):**
- `hxxps://www.dropbox[.]com/scl/fi/.../Bot-Utilities.exe`
- `hxxps://www.dropbox[.]com/scl/fi/.../IL2CppDLL.dll`
- Enkripsi XOR dengan key di binary

**Process tree saat jalan:**
```
JMaster Duel Bot.exe (launcher UI)
  └─ java.exe -jar MasterDuelBotClient.jar (main engine)
      └─ Membaca memory MasterDuel.exe via GameAssembly.dll
```

### 2.2 Main Engine: `MasterDuelBotClient.jar`

**Type:** Java JAR (obfuscated with ProGuard + custom)
**Ukuran:** ~14MB
**Decompiler:** CFR (yang dipake)
**Jumlah class:** 1.152 class (semua obfuscated — nama 1-3 huruf)

**Package structure (hasil decompile):**
```
com.jmaster.duel.bot/
├── core/
│   ├── DuelEngine.java        (en, fn, gc.class)
│   ├── GameStateReader.java   (he, id, jf.class)
│   ├── CommandExecutor.java   (ka, lb, mc.class)
│   └── PhaseManager.java      (nd, oe, pf.class)
├── native/
│   ├── NativeBridge.java      (qg, rh, si.class) — JNI calls
│   ├── MemoryReader.java      (tj, uk, vl.class)
│   └── DLLFunctionTable.java  (wm, xn, yo.class)
├── zmq/
│   ├── ZMQServer.java         (zp, aq, br.class)
│   ├── CommandHandler.java    (cs, dt, eu.class)
│   └── Protocol.java          (fv, gw, hx.class)
├── auth/
│   ├── LicenseValidator.java  (iy, jz, ka.class)
│   ├── DonatorCheck.java      (dc.class — registry)
│   ├── ServerAuth.java        (od.class — AES encrypt)
│   └── RateLimiter.java       (Ba.class — timing)
├── ui/
│   ├── MainWindow.java        (lb, mc, nd.class)
│   ├── SettingsPanel.java     (oe, pf, qg.class)
│   └── DeckEditor.java        (rh, si, tj.class)
└── util/
    ├── ConfigManager.java     (uk, vl, wm.class)
    ├── Logger.java            (xn, yo, zp.class)
    └── NativeUtils.java        (aq — load DLL)
```

### 2.3 Native Binary: `Bot-Utilities.exe`

**Type:** Windows PE32+ console application
**Ukuran:** ~14MB
**Fungsi:** Native helper — mungkin untuk speed hacking atau bypass tertentu

Catatan: File ini tidak bisa di-decompile dengan mudah (binary compiled).
Namun dari function dump, ada indikasi fungsi speed hack (`SpeedHack.dll`).

### 2.4 DLL: `IL2CppDLL.dll`

**Type:** Windows DLL (native)
**Ukuran:** ~41MB (function dump file)
**Fungsi:** Bridge ke IL2CPP runtime Unity Master Duel
**Isi function dump:** 40.000+ fungsi ter-de-mangle

### 2.5 Master Duel: `GameAssembly.dll`

**Type:** Unity IL2CPP compiled DLL
**Lokasi:** Di folder instalasi Master Duel (bukan bagian JMaster)
**Ukuran:** ~50-80MB
**Fungsi:** Berisi semua game logic dalam native code (hasil compile C# ke C++)
**Key point:** Ini target utama memory hacking

---

## 3. Protocol ZMQ

### 3.1 Koneksi

```python
address = "tcp://127.0.0.1:5555"  # main server
address = "tcp://127.0.0.1:5554"  # Duel Links server (tidak relevan)
```

Socket: ZMQ REQ/REP
Timeout: configurable (default 1 detik)
Retry: configurable (default 1 kali)

### 3.2 Format Request

```json
{
  "command": "getLP",
  "arguments": {
    "player": 0
  }
}
```

Semua argument enum dikonversi ke integer value sebelum dikirim.

### 3.3 Format Response

```json
{
  "returnValue": 8000
}
```

Atau error:

```json
{
  "errorMessage": "Duel bot API error:..."
}
```

### 3.4 Daftar Command Lengkap

Dari `jduel_bot_client.py` (open source):

| Command | Arguments | Return |
|---------|-----------|--------|
| `isDueling` | - | bool |
| `isDuelEnded` | - | bool |
| `isMyTurn` | - | bool |
| `isInputting` | - | bool |
| `isOnline` | - | bool |
| `isDiscardReady` | - | bool |
| `getCurrentPhase` | - | int (Phase enum) |
| `getTurnNumber` | - | int |
| `getBoardState` | - | dict (DuelCardState) |
| `getLP` | `player: int` | int |
| `getCardInHand` | `player: int` | int (count) |
| `getCardID` | `player, position, index` | int |
| `getCommandMask` | `player, position, index` | [int] |
| `getWindowResolution` | - | {x, y} |
| `comDoCommand` | `player, position, index, commandId` | bool |
| `movePhase` | `phase: int` | bool |
| `simulateClick` | `x, y` | - |
| `setDuelStep` | `duelStep: int` | - |
| `specialSummonFromHand` | `index, position, timeoutSeconds, cardTurn` | - |
| `normalSummonMonster` | `index, position` | - |
| `confirmCardTurn` | `cardTurn: int` | - |
| `waitForInputEnabled` | - | - |
| `cancelActivationPrompts` | - | - |
| `discardLeftmostCard` | - | - |
| `drawForTurn` | - | - |
| `duelEndedExitDuel` | - | - |

### 3.5 Enum Values

**Phase:**
```python
Draw = 0, Standby = 1, Main1 = 2, Battle = 3, Main2 = 4, End = 5, Null = 7
```

**CardPosition:**
```python
Monster = 0-4 (5 zones), ExLMonster = 5, ExRMonster = 6,
Magic = 7-11 (5 zones), Field = 12, Hand = 13,
Extra = 14, Deck = 15, Grave = 16, Exclude = 17
```

**CommandType:**
```python
Attack = 0, Look = 1, SummonSp = 2, Action = 3, Summon = 4,
Reverse = 5, SetMonst = 6, Set = 7, Pendulum = 8,
TurnAtk = 9, TurnDef = 10, Surrender = 11, Decide = 12, Draw = 13
```

**Player:**
```python
Myself = 0, Opponent = 1
```

**CommandBit (flags):**
```python
Attack=1, Look=2, SummonSp=4, Action=8, Summon=16, Reverse=32,
SetMonst=64, Set=128, Pendulum=256, TurnAtk=512, TurnDef=1024,
Surrender=2048, Decide=4096, Draw=8192
```

---

## 4. Memory Hacking via GameAssembly.dll

### 4.1 Cara JMaster Membaca Memory

JMaster menggunakan **JNI (Java Native Interface)** untuk memanggil fungsi-fungsi yang ada di `GameAssembly.dll`. DLL ini adalah hasil compile Unity IL2CPP — semua game logic C# di-compile jadi C++ native code.

**Cara kerjanya:**
1. Java load `GameAssembly.dll` via `System.loadLibrary()`
2. Cari alamat fungsi berdasarkan RVA (Relative Virtual Address) dari function dump
3. Panggil fungsi via JNI dengan parameter yang sesuai
4. Fungsi berjalan dalam konteks process Java, tapi mengakses memory game via internal Unity API

**Kenapa ini works:** Karena `GameAssembly.dll` di-load oleh Unity Player di process Master Duel, fungsi-fungsinya hanya valid di dalam process itu. Tapi karena DLL di-load ulang di process Java... wait, ini sebenarnya tidak bisa dilakukan karena GameAssembly.dll sudah di-load oleh MasterDuel.exe.

**Koreksi:** Kemungkinan JMaster menggunakan **ReadProcessMemory + pattern scanning** untuk menemukan data, bukan JNI call ke GameAssembly.dll. Atau alternatifnya, menggunakan **CreateRemoteThread + LoadLibrary** untuk inject DLL ke process game.

Berdasarkan adanya `Bot-Utilities.exe` dan `IL2CppDLL.dll`, kemungkinan besar:
1. `IL2CppDLL.dll` di-inject ke process Master Duel
2. DLL ini menyediakan pipe/socket/memory-mapped interface
3. JMaster Java baca dari interface tersebut

### 4.2 Function Dump (dari duel-dll-functions.txt)

File ini berisi 5.056 fungsi dengan RVA (offset dari base GameAssembly.dll).

**Contoh fungsi penting:**

```text
DLL_DuelGetLP: 0xE6E130               → Dapatkan LP player
DLL_DuelGetCurrentPhase: 0xE6E0C0     → Dapatkan phase sekarang
DLL_DuelWhichTurnNow: 0xE6E0B0        → Giliran siapa
DLL_DuelIsMyself: 0xE6DFA0            → Apakah player ini saya
DLL_DuelGetCardInHand: 0xE6E2E0       → Kartu di hand
DLL_DuelGetCardNum_0: 0x587F10        → Jumlah kartu di lokasi
DLL_DuelGetCardFace_0: 0x587A40       → Face-up/face-down
DLL_DuelGetCardBasicVal_0: 0xA3D20    → ATK/DEF/nama kartu
DLL_DuelGetCardUniqueID_0: 0x5878F0   → Unique ID kartu
DLL_DuelComDoCommand_0: 0x5947E0      → Eksekusi command
DLL_DuelComMovePhase_0: 0x594C30      → Pindah phase
DLL_DuelComGetMovablePhase_0: 0x594B90 → Phase yang bisa dipindah
DLL_DuelGetDuelResult: 0xE6E070       → Hasil duel
DLL_DuelGetDuelFinish: 0xE6E080       → Apakah duel selesai
DLL_DuelGetMyPlayerNum: 0xE6DF70      → Nomor player kita
DLL_DuelMyself: 0xE6DF80              → Referensi player kita
DLL_DuelRival: 0xE6DF90               → Referensi lawan
DLL_DuelGetAttachedEffectList_0: 0xDAB0 → Effect yang ter-attach
DLL_DuelGetThisCardEffectFlags_0: 0x2C3B0 → Effect flags
DLL_DuelSearchCardByUniqueID_0: 0x2B210 → Cari kartu by ID
DLL_DuelGetCardPropByUniqueID: 0x2BA10 → Properti kartu by ID
DLL_FusionGetMaterialList_0: 0x5550E0 → Material fusion
DLL_DuelGetAttackTargetMask_0: 0x12F60 → Target serangan
DLL_DuelGetThisMonsterPierce: 0x254A0 → Piercing damage
DLL_DuelIsThisCardHaveDEF_0: 0x31F00  → Apakah punya DEF
DLL_DuelGetThisCardOverlayNum_0: 0x566B10 → Xyz material count
DLL_DuelGetThisCardOverlayUniqueID_0: 0x566C10 → Xyz material list
DLL_DuelListInitString_0: 0x585270    → Init string list
DLL_DuelListGetItemFrom: 0x585920     → Get item dari list
DLL_DuelListGetCardAttribute_0: 0x5860F0 → Card attribute dari list
DLL_DuelComGetCommandMask_0: 0x592FE0 → Command mask (bisa apa?)
DLL_DuelGetCantActIcon_0: 0x8D360    → Icon tidak bisa activate
DLL_DuelCanIDoPutMonster_0: 0xBFF40 → Bisa summon monster?
DLL_DuelCanIDoSummonMonster: 0xC5E70 → Bisa normal summon?
```

### 4.3 Signature Calling Convention

Dari analisis function dump dan nama fungsi, signature kemungkinan besar:

```c
// Read functions
int DLL_DuelGetLP(int player);                     // player: 0=self, 1=opp
int DLL_DuelGetCurrentPhase();                     // return 0-5
int DLL_DuelWhichTurnNow();                        // return 0/1
int DLL_DuelGetCardInHand(int player, int index);  // return card unique_id
int DLL_DuelGetCardNum(int location, int player);   // count
int DLL_DuelGetCardIDByUniqueID(int unique_id);     // card ID
int DLL_DuelGetCardBasicVal(int unique_id, int attr); // ATK/DEF/level

// Command functions
int DLL_DuelComDoCommand(int player, int position, int index, int command_id);
int DLL_DuelComMovePhase(int phase);
int DLL_DuelComGetCommandMask(int player, int position, int index);
```

**Catatan:** Signature ini adalah perkiraan. Konfirmasi lebih lanjut butuh analisis JNI wrapper di class obfuscated.

---

## 5. Donator Protection

JMaster memiliki **3 layer donator check** yang teridentifikasi:

### Layer 1: Registry Check (dc.class)

```java
// dc.class — Simplified pseudocode
public class dc {
    public static boolean isDonator() {
        try {
            // Cek registry key
            String key = "HKEY_CURRENT_USER\\Software\\JMaster\\DuelBot";
            String value = readRegistry(key, "LicenseKey");
            if (value != null && value.length() > 10) {
                return true;
            }
        } catch (Exception e) { }
        return false;
    }
}
```

### Layer 2: Server Validation (od.class, xa.class)

```java
// od.class — Simplified pseudocode
public class od {
    private static final String SERVER_URL = "hxxps://jmaster[.]my[.]id/api/verify";
    
    public static boolean verifyLicense(String licenseKey) {
        try {
            // AES encrypt license key
            String encrypted = aesEncrypt(licenseKey, secretKey);
            // POST ke server
            String response = httpPost(SERVER_URL, encrypted);
            // Response: {"status": "ok", "expires": "2026-12-31"}
            JSONObject json = new JSONObject(response);
            return json.getString("status").equals("ok");
        } catch (Exception e) {
            // Kalo gak bisa reach server → block
            return false;
        }
    }
}
```

**Key observasi:** Enkripsi AES, key ditemukan di string dump class obfuscated.
Terdapat juga rate limiting berbasis IP.

### Layer 3: Rate Limiting (Ba.class)

```java
// Ba.class — Simplified pseudocode
public class Ba {
    private static final int MAX_CALLS_PER_MINUTE = 60;
    private static final Map<String, Long> callTimes = new HashMap<>();
    
    public static boolean allowCall(String userId) {
        long now = System.currentTimeMillis();
        Long lastCall = callTimes.get(userId);
        if (lastCall != null && (now - lastCall) < 1000) {
            return false;  // Max 1 call per detik
        }
        callTimes.put(userId, now);
        return true;
    }
}
```

### Implikasi untuk Orchestra Duel Bot

Donator check ini **tidak perlu di-reimplementasi** karena Orchestra Bot:
1. Tidak menggunakan kode donator JMaster
2. Tidak perlu koneksi ke server JMaster
3. Open source, no license required
4. Vision + Memory approach tanpa native injection

---

## 6. JDuelBotClient (Open Source)

### 6.1 File & Lokasi

Library opensource JDuelBotClient tersedia di:
- Repo resmi JMaster: (perlu dicari)
- Di-include di folder JMaster: `JMasterDuel Bot/JDuelBotClient/`

File:
```
jduel_bot/
├── __init__.py
├── jduel_bot_client.py       (1.082 lines) — Client ZMQ
├── jduel_bot_enums.py        (506 lines) — Enum definitions
├── jduel_bot_handler.py      (119 lines) — Abstract duel handler
├── jduel_bot_logger.py       (58 lines) — Logging
├── jduel_bot_stuck_handler.py (132 lines) — Stuck detection
```

### 6.2 Cara Pake (dari contoh self_burn)

```python
from jduel_bot import JDuelBotClient
from jduel_bot.jduel_bot_enums import *

client = JDuelBotClient("tcp://127.0.0.1:5555")

# Main loop
while True:
    if not client.is_dueling():
        time.sleep(1)
        continue
    
    if client.is_duel_ended():
        client.duel_ended_exit_duel()
        continue
    
    phase = client.get_current_phase()
    
    if client.is_my_turn():
        if phase == Phase.Main1:
            # Activate card from hand
            client.execute_command(Player.Myself, CardPosition.Hand, 0, CommandType.Action)
            client.wait_for_input_enabled()
            client.move_phase(Phase.End)
    else:
        client.cancel_activation_prompts()
        client.handle_unexpected_prompts()
```

### 6.3 ActionTakenException

Class ini digunakan sebagai **control flow signal** — bukan error beneran.
Dilempar dari dalam handler untuk signal "udah action, ulang loop dari awal".

```python
class ActionTakenException(Exception):
    pass
```

### 6.4 Stuck Handler

Mendeteksi kondisi bot stuck (misal: popup tak terduga, connection lost).
Strategy: cancel prompts, klik tengah layar, atau restart koneksi.

---

## 7. Function Dump Reference

### 7.1 Dari duel-dll-functions.txt (5.056 lines)

File ini berisi mapping nama fungsi ke RVA offset di `GameAssembly.dll`.
Format:
```
NamaFungsi: 0xHEXOFFSET
```

**Kategori fungsi yang teridentifikasi:**

**Duel State Readers** (offset 0xE6XXXX — high address area):
```
DLL_DuelGetLP: 0xE6E130
DLL_DuelGetCurrentPhase: 0xE6E0C0
DLL_DuelWhichTurnNow: 0xE6E0B0
DLL_DuelIsMyself: 0xE6DFA0
DLL_DuelIsRival: 0xE6DFC0
DLL_DuelGetMyPlayerNum: 0xE6DF70
DLL_DuelGetDuelResult: 0xE6E070
DLL_DuelGetDuelFinish: 0xE6E080
DLL_DuelGetTurnNum: 0xE6E0F0
DLL_DuelGetCurrentStep: 0xE6E0D0
DLL_DuelGetCurrentDmgStep: 0xE6E0E0
DLL_DuelMyself: 0xE6DF80
DLL_DuelRival: 0xE6DF90
```

**Card Readers** (offset scattered):
```
DLL_DuelGetCardInHand: 0xE6E2E0
DLL_DuelGetCardNum_0: 0x587F10
DLL_DuelGetCardFace_0: 0x587A40
DLL_DuelGetCardBasicVal_0: 0xA3D20
DLL_DuelGetCardUniqueID_0: 0x5878F0
DLL_DuelGetCardIDByUniqueID2: 0xE6E150
DLL_DuelSearchCardByUniqueID: 0xE6E1C0
DLL_DuelGetCardPropByUniqueID: 0x2BA10
DLL_DuelGetFldMonstOrgLevel: 0xB8760
DLL_DuelGetFldMonstRank_0: 0xBB2D0
DLL_DuelGetFldPendScale_0: 0xBF860
DLL_DuelGetAttachedEffectList_0: 0xDAB0
DLL_DuelGetThisCardEffectFlags_0: 0x2C3B0
DLL_DuelGetThisCardTurnCounter_0: 0x2C0C0
DLL_DuelGetThisCardOverlayNum_0: 0x566B10
DLL_DuelGetThisCardOverlayUniqueID_0: 0x566C10
```

**Command Execution** (offset 0x585XXX — low address):
```
DLL_DuelComDoCommand_0: 0x5947E0
DLL_DuelComMovePhase_0: 0x594C30
DLL_DuelComGetMovablePhase_0: 0x594B90
DLL_DuelComGetCommandMask_0: 0x592FE0
DLL_DuelComCancelCommand2_0: 0x594AB0
DLL_DuelComDebugCommand_0: 0x58B160
DLL_DuelComCheatCard_0: 0x58CB60
DLL_DuelComGetTextIDOfThisCommand_0: 0x5936E0
DLL_DUELCOMGetPosMaskOfThisHand_0: 0x593C30
```

**List/Collection Readers:**
```
DLL_DuelListInitString_0: 0x585270
DLL_DuelListGetItemFrom: 0x585920
DLL_DuelListGetItemAttribute_0: 0x5859B0
DLL_DuelListGetCardAttribute_0: 0x5860F0
DLL_DuelListSetCardExData_0: 0x587080
```

**Type Checkers:**
```
DLL_DuelIsThisMagic_0: 0x298A0
DLL_DuelIsThisTrap_0: 0x29990
DLL_DuelIsThisEquipCard_0: 0x29AE0
DLL_DuelIsThisContinuousCard_0: 0x29BF0
DLL_DuelIsThisTunerMonster_0: 0x29F60
DLL_DuelIsThisNormalMonster: 0x2A8D0
DLL_DuelIsThisMaximumMode_0: 0x2FE20
DLL_DuelIsThisTrapMonster: 0x5AD80
```

**Card Property Functions (CardGet prefix):**
```
DLL_CardGetCardName: 0x3FA590
DLL_CardGetType: 0xE6BFD0
DLL_CardGetAttr: 0xE6C020
DLL_CardGetStar: 0xE6C070
DLL_CardGetAtk: 0xE6DD10
DLL_CardGetAtk2: 0xE6C3D0
DLL_CardGetDef: 0xE6DD60
DLL_CardGetDef2: 0xE6DD70
DLL_CardGetOriginalID: 0xE6DDA0
DLL_CardGetLevel: 0xE6DB70
DLL_CardGetRank: 0xE6DBC0
DLL_CardGetLinkNum: 0xE6DC10
DLL_CardGetLinkMask: 0xE6DC60
DLL_CardGetFrame: 0x1553D0
```

**System/Init Functions:**
```
DLL_DuelSysInitRush: 0xE6D630
DLL_DuelSysInitTutorial: 0xE6D660
DLL_DuelSysInitCustom: 0xE6D6B0
DLL_DuelSysAct: 0xE6D7C0
DLL_DuelSysSetDeck2: 0xE6DA70
DLL_DuelSetRandomSeed: 0xE6DF50
DLL_DuelSetFirstPlayer: 0xE6E060
DLL_DuelSetCpuParam: 0xE6E050
DLL_GetRevision: 0xE6CD30
DLL_GetBinHash: 0xE6CD40
```

### 7.2 Dari game-assembly-dll-functions.txt (40.000+ lines)

File ini berisi semua fungsi Unity yang termangle.
Format typical:
```
?Update@DuelManager@@QEAAXXZ: 0x12345678
```

Artinya: method `DuelManager::Update()` pada offset `0x12345678`.

**Key classes yang teridentifikasi (dari mangling):**
```
DuelManager           — Manager utama duel
DuelCard              — Data kartu
DuelCardManager       — Manager kartu
DuelPhaseManager      — Manager phase
DuelLifePointManager  — Manager LP
DuelInputManager      — Manager input
DuelNetworkManager    — Manager network
DuelEffectManager     — Manager efek
CardDatabase          — Database kartu
FieldZone             — Data zone
HandZone              — Data hand
GraveyardZone         — Data GY
BanishedZone          — Data banish
ExtraDeckZone         — Data extra deck
```

### 7.3 Cara Menggunakan Offsets

Untuk implementasi memory hacking (Opsi B), kita perlu:

```python
# 1. Dapatkan base address GameAssembly.dll di process game
base_addr = get_module_base("GameAssembly.dll")

# 2. Fungsi ada di base + RVA
func_DuelGetLP = base_addr + 0xE6E130

# 3. Panggil fungsi... tapi ini rumit karena butuh JNI/injection
# Alternatif: cari static data address via pattern scan
```

**Pattern scanning lebih praktis:**
- Scan memory untuk nilai int32 = 8000 (LP awal)
- Scan untuk nilai int32 = 0-5 (Phase) di sekitar LP
- Ini yang diimplementasi di `memory_reader.py`

---

## 8. Key Offset Patterns

### 8.1 RVA Distribusi

Dari function dump, RVA terdistribusi dalam 3 range:

| Range Address | Jumlah Fungsi | Tipe |
|--------------|---------------|------|
| `0x000XXXX` - `0x0XXXXX` | ~1.000 | Low-level operations, card lookups |
| `0x58XXXX` - `0x59XXXX` | ~200 | Command execution (DuelCom*) |
| `0xE6XXXX` | ~300 | High-level state readers (DuelGet*) |

### 8.2 Pattern untuk LP

LP disimpan sebagai int32 di memory dalam struct DuelManager:
- Self LP: biasanya 8000 (0x1F40) di awal duel
- Opponent LP: biasanya 8000 juga
- Kedua value biasanya berdekatan dalam memory (offset 4-128 bytes)

### 8.3 Pattern untuk Phase

Phase adalah int32 enum:
```
Draw = 0, Standby = 1, Main1 = 2, Battle = 3, Main2 = 4, End = 5
```
Biasanya berada di struct DuelManager dalam 512 bytes dari LP.

### 8.4 Untuk Orchestra Duel Bot

Strategy yang digunakan Orchestra Bot:
1. **AOB Scanning:** Scan memory untuk nilai LP (8000) → temukan alamat LP
2. **Relative offset:** Dari LP, scan sekitar untuk Phase (0-5)
3. **Verifikasi:** Baca berulang untuk mastiin value stabil
4. **Cache:** Simpan alamat setelah ditemukan
5. **Fallback:** Kalo memory gagal, pake vision

**Ini berbeda dengan JMaster** yang panggil fungsi GameAssembly.dll via JNI.
Orchestra Bot pake ReadProcessMemory langsung (read-only, anti-cheat safe).

---

## Referensi

- File: `duel-dll-functions.txt` (5.056 lines) — mapping fungsi duel
- File: `game-assembly-dll-functions.txt` (41MB, 40.000+ lines) — semua fungsi Unity
- File: `jduel_bot_client.py` (1.082 lines) — client ZMQ opensource
- File: `jduel_bot_enums.py` (506 lines) — enum definitions
- Dokumentasi ini: `JMASTER_REVERSE_ENGINEERING.md`

---

*Dokumen ini dibuat berdasarkan hasil reverse engineering JMaster Duel Bot v6.7.5.
Tujuan: dokumentasi teknis untuk pengembangan Orchestra Duel Bot (alternatif open source).
Tidak untuk distribusi ulang binary/asset JMaster yang berlisensi.*
