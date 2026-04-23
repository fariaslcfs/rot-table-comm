# Mesa Inercial IEAv — Controle via Modbus TCP (Python Interface)

## Visão Geral

Este documento descreve a interface de controle da mesa inercial de 2 eixos (Yaw e Roll) utilizada no IEAv, operando via protocolo **Modbus TCP**.

A abordagem substitui o sistema original em C (com dependência de compilação, Mongoose server e frontend JS) por uma solução direta em Python, simplificando manutenção, testes e integração.

### Parâmetros de conexão

- IP padrão do controlador: `192.168.1.1`
- Porta: `502`
- Protocolo: Modbus TCP

---

## Princípios de operação

- Todas as posições e velocidades são enviadas em **unidades de engenharia escaladas**
- Escalas utilizadas:
  - Velocidade: `valor × 100`
  - Posição: `valor × 1000`
- Registradores de 32 bits são divididos em dois registradores de 16 bits:
  - LOW = `value & 0xFFFF`
  - HIGH = `value >> 16`

---

## Estrutura de registradores (Controlador da mesa)

### Controle de movimento

| Endereço | Função | Descrição |
|----------|--------|-----------|
| 20 | Emergency Stop | 4 = stop imediato / 0 = reset |
| 22 | Enable Roll | 0 off / 1 on / 2 reverse |
| 24 | Enable Yaw | 0 off / 1 on / 2 reverse |
| 26 | Roll Command | 0 stop / 1 forward / 2 reverse / 4 mode pos |
| 28 | Yaw Command | 0 stop / 1 forward / 2 reverse / 4 mode pos |

---

### Configuração de movimento (posicionamento)

| Endereço | Função |
|----------|--------|
| 40 | Roll acceleration |
| 42 | Roll max acceleration |
| 50 | Yaw acceleration |
| 52 | Yaw max acceleration |
| 60 | Roll position (LOW/HIGH 32-bit) |
| 70 | Yaw position (LOW/HIGH 32-bit) |

---

### Velocidade (jog / controle contínuo)

| Endereço | Função |             Observação               |
|----------|--------|--------------------------------------|
| 46 e 47| Roll velocity (16-bit) | Somente 46 usado |
| 56 e 56| Yaw velocity (16-bit) | Somente 56 usado |

---

### Limites e parâmetros adicionais

| Endereço | Função |
|----------|--------|
| 62 | Roll velocity position |
| 64 | Roll acceleration position |
| 72 | Yaw velocity position |
| 74 | Yaw acceleration position |
| 76 | Yaw acceleration (extra) |
| 80 | Roll max velocity |
| 82 | Roll max acceleration |
| 90 | Yaw max velocity |
| 92 | Yaw max acceleration |

---

## Regras importantes de operação

### Sequência de posicionamento

Para garantir operação correta do controlador da mesa:

1. Habilitar eixo:
   - Roll: `22 = 2`
   - Yaw: `24 = 2`

2. Reset comando:
   - `26 = 0` (Roll)
   - `28 = 0` (Yaw)

3. Enviar posição (32 bits split)

4. Configurar aceleração

5. Ativar modo posição:
   - `26 = 4` (Roll)
   - `28 = 4` (Yaw)

---

### Sequência de velocidade (jog)

1. Configuração base:
   - `22 = 1`
   - `24 = 1`
   - `40 = 10000`
   - `42 = 10000`
   - `50 = 10000`
   - `52 = 10000`

2. Envio de velocidade:
   - Roll: `46` (×100)
   - Yaw: `56` (×100)

3. Direção:
   - 0 = stop
   - 1 = forward
   - 2 = reverse

---

## Formato de registradores 32 bits (2 registradores de 16 bits)
* O modbus é um protocolo com palavras de 16 bits.

Alguns registradores exigem divisão em dois registradores de 16 bits.

### Regra

~~~c
uint16_t LOW  = value & 0xFFFF;
uint16_t HIGH = value >> 16;
~~~

### Exemplo prático

Valor:

- 90000

Conversão:

- Hex: 0x00015F90

Resultado:

- LOW = 24464
- HIGH = 1

---

## Observações de protocolo

- O firmware original em C abre e fecha conexão Modbus a cada comando
- A implementação Python pode manter conexão persistente
- Alguns comandos exigem delays (~20ms) entre operações
- Comando de posição exige transição: 0 → 4

---

## Convenções físicas

- Yaw = eixo horizontal (yaw)
- Roll = eixo vertical (pitch)
- Posição: graus × 1000
- Velocidade: graus/s × 100

---

## Resumo operacional

### Movimentos suportados

- Posicionamento absoluto
- Jog contínuo
- Stop imediato
- Controle independente ou combinado de eixos

---

## Nota de engenharia

Este mapeamento foi obtido por engenharia reversa do controlador da mesa IEAv e validado empiricamente via Modbus TCP.

A arquitetura atual elimina dependências do sistema legado e permite controle direto via Python com comportamento equivalente ao firmware original.


# 👥 Equipe
**Roney e EFO-S**
