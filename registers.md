## 🔹 Input Registers (Somente leitura)
| Endereço 16 bits | Conteúdo |
|----------|----------|
| 0-1 | POS_AZI |
| 2-3 | VEL_AZI |
| 4-5 | POS_TILT |
| 6-7 | VEL_TILT |

## 🔹 Holding Registers
| Endereço 16 bits | Nome | Descrição |
|----------|------|----------|
| 22 | ENABLE | Habilitação geral |
| 24 | ENABLE | Habilitação geral |
| 28 | CMD_AZI | 0=stop, 1=+, 2=-, 4=pos |
| 26 | CMD_TILT | 0=stop, 1=+, 2=-, 4=pos |
| 46-47 | VEL_TILT_CMD | Velocidade Tilt |
| 56-57 | VEL_AZI_CMD | Velocidade Azimute |
| 60-61 | TARGET_TILT | Posição alvo Tilt |
| 70-71 | TARGET_AZI | Posição alvo Azimute |
| 72 | VPosAzi | Velocidade pos. Azimute |
| 74 | APosAzi | Aceleração Azimute |
| 62 | VPosTilt | Velocidade pos. Tilt |
| 64 | APosTilt | Aceleração Tilt |
| 80 | MaxVelTitl | Tilt max velocity |
| 82 | MaxAccTilt | Tilt max acceleration |
| 90 | MaxVelAzi | Azimuth max velocity |
| 92 | MaxAccAzi | Azimuth max acceleration |