# 🔄 Command Flow Specification — RotTableWrapper

Este documento descreve **todos os fluxos de comando** implementados na classe `RotTableWrapper`, baseando-se **exclusivamente no comportamento do código**.

---

# 🧭 Visão Geral

```text
START → connect → selecionar operação → executar sequência → END
```

## Tipos de operação

* MOVE (posicionamento absoluto)
* JOG (velocidade contínua)
* STOP
* READ (feedback)
* EMERGENCY

---

# ⚙️ 1. PREPARAÇÃO (BASE DO SISTEMA)

## prepare_yaw_motion / prepare_roll_motion

```text
write(addr_acc, acc_reg_value)
write(addr_maxacc, acc_reg_value)

write(22, 1)
delay 0.1 s   ⚠️ CRÍTICO

write(24, 1)
delay 0.1 s   ⚠️ CRÍTICO
```

## prepare_all_motion

```text
prepare_yaw_motion()
prepare_roll_motion()
```

---

# 🎯 2. MOVE (POSICIONAMENTO)

## ▶ move_yaw(angle)

```text
prepare_yaw_motion()

write(24, 2)           # modo posição
write(28, 0)           # stop/reset

write_dword(70, pos)

delay 0.02 s

write(28, 4)           # trigger
```

---

## ▶ move_roll(angle)

```text
prepare_roll_motion()

write(22, 2)
write(26, 0)

write_dword(60, pos)

delay 0.02 s

write(26, 4)
```

---

## ▶ move_all(angle)

```text
prepare_all_motion()

write(24, 2)
write(22, 2)

write(28, 0)
write(26, 0)

write_dword(70, pos yaw)
write_dword(60, pos roll)

delay 0.02 s

write(28, 4)
write(26, 4)
```

---

# 🚀 3. JOG (VELOCIDADE)

## ▶ jog_yaw(vel)

```text
prepare_yaw_motion()

write_dword(56, |vel|)

vel > 0 → write(28, 1)
vel < 0 → write(28, 2)
vel = 0 → write(28, 0)
```

---

## ▶ jog_roll(vel)

```text
prepare_roll_motion()

write_dword(46, |vel|)

vel > 0 → write(26, 1)
vel < 0 → write(26, 2)
vel = 0 → write(26, 0)
```

---

## ▶ jog_all(vel)

```text
prepare_all_motion()

write_dword(56, |vel|)
write_dword(46, |vel|)

YAW:
  vel > 0 → write(28, 1)
  vel < 0 → write(28, 2)
  vel = 0 → write(28, 0)

ROLL:
  vel > 0 → write(26, 1)
  vel < 0 → write(26, 2)
  vel = 0 → write(26, 0)
```

---

# 🛑 4. STOP

## ▶ stop_yaw

```text
write(28, 0)
```

## ▶ stop_roll

```text
write(26, 0)
```

## ▶ stop_all

```text
write(28, 0)
write(26, 0)
```

---

# 📡 5. LEITURA (FEEDBACK)

## ▶ get_yaw

```text
read_input(0, 2)

value = (MSB << 16) | LSB

return value / 1_000_000
```

---

## ▶ get_roll

```text
read_input(4, 2)

value = (MSB << 16) | LSB

return value / 1_000_000
```

---

## ▶ get_both_axes

```text
yaw  = get_yaw()
roll = get_roll()

return (yaw, roll)
```

---

# 🚨 6. EMERGENCY

## ▶ emergency_stop

```text
write(20, 4)

delay 0.2 s

write(20, 0)
```

---

## ▶ reset_emergency

```text
write(20, 1)

delay 0.2 s

write(20, 0)
```

---

# 🧠 RESUMO OPERACIONAL

```text
PREPARE:
write → delay → write → delay

MOVE:
prepare → mode → stop → position → delay → trigger

JOG:
prepare → velocity → direction

STOP:
direction = 0

READ:
read → merge → convert

EMERGENCY:
write → delay → write
```

---

# ⚠️ PONTOS CRÍTICOS

* delays de **0.1 s são obrigatórios** na preparação
* delay de **0.02 s é necessário antes do trigger**
* não existe loop no código Python
* cada comando é uma sequência discreta
* `write_dword` sempre escreve 2 registradores (LSB/MSB)
* STOP atua apenas zerando direção
* `*_all` replica comandos para ambos eixos

---

# 🧱 ARQUITETURA DO CÓDIGO

## Nível 1 — CORE

```text
write
write_dword
read_input
```

## Nível 2 — PRIMITIVOS

```text
set_*
normalize
clip
```

## Nível 3 — SEQUÊNCIA

```text
prepare_*
move_*
jog_*
stop_*
get_*
```

---

# ✅ USO PRÁTICO

## Sequência típica (MOVE)

```text
connect
→ move_all(ângulo)
→ (movimento ocorre)
```

## Sequência típica (JOG)

```text
connect
→ jog_all(velocidade)
→ stop_all()
```

## Sequência típica (READ)

```text
connect
→ get_both_axes()
```
