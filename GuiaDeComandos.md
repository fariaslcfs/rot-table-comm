# RotTableWrapper — Guia Expandido com Fluxogramas

> Controle da mesa inercial IEAv (Yaw + Roll) via Modbus TCP  
> Inclui fluxos completos de execução (command flow)

---

# 1. VISÃO GERAL

A arquitetura de controle segue um padrão determinístico baseado em sequência:

```
PREPARE → MODE → WRITE → DELAY → TRIGGER
```

Aplicado a:
- Movimento absoluto (MOVE)
- Movimento contínuo (JOG)
- Leitura (READ)
- Parada (STOP)

---

# 2. FLUXO GLOBAL

```
                ┌──────────────┐
                │   INÍCIO     │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │   PREPARE    │
                └──────┬───────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
     MOVE            JOG            READ
        │              │              │
        ▼              ▼              ▼
   TRIGGER         DIREÇÃO        RETURN
        │              │
        └──────┬───────┘
               ▼
           STOP (opcional)
```

---

# 3. PREPARAÇÃO (BASE DE TUDO)

Executado implicitamente em:
- move_*
- jog_*

```
prepare_yaw_motion() / prepare_roll_motion()

write(acc)
write(max_acc)

write(enable_roll = 1)
delay(0.1)   ⚠️ obrigatório

write(enable_yaw = 1)
delay(0.1)   ⚠️ obrigatório
```

Fluxograma:

```
[START]
   │
   ▼
write ACC
   │
write MAX_ACC
   │
write ENABLE ROLL
   │
delay 0.1s
   │
write ENABLE YAW
   │
delay 0.1s
   │
   ▼
[READY]
```

---

# 4. MOVE (POSICIONAMENTO ABSOLUTO)

## 4.1 YAW

```
move_yaw(angle)
```

Fluxo:

```
PREPARE
   │
   ▼
SET MODE (posição)
   │
   ▼
STOP (direção = 0)
   │
   ▼
WRITE POSITION
   │
   ▼
DELAY 0.02s
   │
   ▼
TRIGGER (4)
```

Fluxograma:

```
[START]
   │
   ▼
prepare_yaw_motion
   │
   ▼
set_position_mode_yaw
   │
   ▼
set_yaw_direction(0)
   │
   ▼
set_yaw_position(angle)
   │
   ▼
delay 0.02s
   │
   ▼
set_yaw_direction(4)
   │
   ▼
[END]
```

---

## 4.2 ROLL

```
move_roll(angle)
```

Fluxo idêntico ao Yaw:

```
prepare → mode → stop → write → delay → trigger
```

---

## 4.3 MOVIMENTO SIMULTÂNEO

```
move_all(angle)
```

Fluxo:

```
prepare_all
   │
set mode yaw + roll
   │
stop ambos
   │
write posição yaw + roll
   │
delay
   │
trigger yaw + roll
```

Fluxograma:

```
[START]
   │
   ▼
prepare_all_motion
   │
   ▼
set_position_mode_yaw
set_position_mode_roll
   │
   ▼
set_yaw_direction(0)
set_roll_direction(0)
   │
   ▼
set_yaw_position(angle)
set_roll_position(angle)
   │
   ▼
delay 0.02s
   │
   ▼
trigger yaw (4)
trigger roll (4)
   │
   ▼
[END]
```

---

# 5. JOG (VELOCIDADE CONTÍNUA)

## 5.1 YAW

```
jog_yaw(vel)
```

Fluxo:

```
prepare
   │
write velocity
   │
define direção:
    vel > 0 → 1
    vel < 0 → 2
    vel = 0 → 0
```

Fluxograma:

```
[START]
   │
   ▼
prepare_yaw_motion
   │
   ▼
set_yaw_velocity(vel)
   │
   ▼
   ┌───────────────┬───────────────┬───────────────┐
   ▼               ▼               ▼
vel > 0         vel < 0         vel = 0
   │               │               │
   ▼               ▼               ▼
dir = 1         dir = 2         dir = 0
   │               │               │
   └───────┬───────┴───────┬───────┘
           ▼               ▼
     set_yaw_direction
           │
           ▼
         [END]
```

---

## 5.2 ROLL

Mesma lógica do Yaw com registradores próprios.

---

## 5.3 JOG SIMULTÂNEO

```
jog_all(vel)
```

Fluxo:

```
prepare_all
   │
write vel yaw + roll
   │
direção independente por eixo
```

---

# 6. STOP

```
stop_yaw()
stop_roll()
stop_all()
```

Fluxo:

```
write(direction = 0)
```

Fluxograma:

```
[ANY STATE]
     │
     ▼
set_direction(0)
     │
     ▼
[STOPPED]
```

---

# 7. LEITURA (FEEDBACK)

## 7.1 POSIÇÃO

```
get_pos_yaw()
get_pos_roll()
get_pos_all()
```

Fluxo:

```
read_input
   │
combine MSB + LSB
   │
to_int32
   │
scale (/1_000_000)
   │
return
```

Fluxograma:

```
[START]
   │
   ▼
read_input_registers
   │
   ▼
combine 32-bit
   │
   ▼
convert signed
   │
   ▼
scale
   │
   ▼
return value
```

---

## 7.2 VELOCIDADE

Mesmo fluxo da posição.

---

# 8. EMERGÊNCIA

```
emergency_stop()
reset_emergency()
```

Fluxo:

```
write(20, X)
delay 0.2
write(20, 0)
```

---

# 9. MATRIZ DE COMANDOS

| Tipo | Sequência |
|------|----------|
| MOVE | prepare → mode → stop → write → delay → trigger |
| JOG  | prepare → velocity → direction |
| READ | read → convert → return |
| STOP | direction = 0 |
| EMERGÊNCIA | write → delay → reset |

---

# 10. PRINCÍPIOS CRÍTICOS

- Sistema é **sequencial e determinístico**
- Delays são **obrigatórios (não remover)**
- Cada comando é **atômico**
- STOP não cancela posição, apenas direção
- *_all garante sincronização entre eixos

---

# 11. EXEMPLO COMPLETO

```
rot = RotTableWrapper("127.0.0.1", 5020)

rot.connect()

# MOVE
rot.move_yaw(30)
rot.move_roll(15)

# JOG
rot.jog_all(20)

# STOP
rot.stop_all()

# LEITURA
yaw, roll = rot.get_pos_all()

# EMERGÊNCIA
rot.emergency_stop()
rot.reset_emergency()

rot.close()
```

---