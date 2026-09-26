# hafta-01 firmware — STM32F407G-DISC1, FreeRTOS 10.3.1, HAL (STM32CubeF4 V1.26.1)
#
# Kullanım (Git Bash):
#   make                 -> build/hafta01.elf/.hex/.bin
#   make flash           -> STM32CubeProgrammer CLI ile ST-LINK üzerinden yükle
#   make clean
#
# Araç zinciri STM32CubeIDE ile gelir; PATH'te yoksa GCC_PATH verin:
#   make GCC_PATH=/c/ST/STM32CubeIDE_1.10.1/STM32CubeIDE/plugins/<gnu-tools>/tools/bin

TARGET   := hafta01
BUILD    := build
PROFILE  ?= O2

ifdef GCC_PATH
PREFIX := $(GCC_PATH)/arm-none-eabi-
else
PREFIX := arm-none-eabi-
endif
CC      := $(PREFIX)gcc
AS      := $(PREFIX)gcc -x assembler-with-cpp
CP      := $(PREFIX)objcopy
SZ      := $(PREFIX)size

PROGRAMMER ?= "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe"

GIT_REV := $(shell git describe --always --dirty 2>/dev/null || echo nogit)

C_SOURCES := \
  $(wildcard App/Src/*.c) \
  $(wildcard Core/Src/*.c) \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_cortex.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_rcc.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_rcc_ex.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_gpio.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_dma.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_uart.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_pwr.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_pwr_ex.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_flash.c \
  Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_flash_ex.c \
  Middlewares/Third_Party/FreeRTOS/Source/tasks.c \
  Middlewares/Third_Party/FreeRTOS/Source/queue.c \
  Middlewares/Third_Party/FreeRTOS/Source/list.c \
  Middlewares/Third_Party/FreeRTOS/Source/portable/GCC/ARM_CM4F/port.c \
  Middlewares/Third_Party/FreeRTOS/Source/portable/MemMang/heap_4.c

ASM_SOURCES := Core/Startup/startup_stm32f407xx.s

C_INCLUDES := \
  -IApp/Inc -ICore/Inc \
  -IDrivers/STM32F4xx_HAL_Driver/Inc \
  -IDrivers/CMSIS/Device/ST/STM32F4xx/Include \
  -IDrivers/CMSIS/Include \
  -IMiddlewares/Third_Party/FreeRTOS/Source/include \
  -IMiddlewares/Third_Party/FreeRTOS/Source/portable/GCC/ARM_CM4F

MCU     := -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
C_DEFS  := -DUSE_HAL_DRIVER -DSTM32F407xx \
           -DFW_GIT_REV=\"$(GIT_REV)\" -DFW_BUILD_PROFILE=\"$(PROFILE)\"

CFLAGS  := $(MCU) $(C_DEFS) $(C_INCLUDES) -$(PROFILE) -g3 -std=gnu11 \
           -Wall -ffunction-sections -fdata-sections -MMD -MP
ASFLAGS := $(MCU) -g3

LDSCRIPT := STM32F407VGTX_FLASH.ld
LDFLAGS  := $(MCU) -specs=nano.specs -specs=nosys.specs -T$(LDSCRIPT) \
            -Wl,-Map=$(BUILD)/$(TARGET).map,--cref -Wl,--gc-sections

OBJECTS := $(addprefix $(BUILD)/,$(notdir $(C_SOURCES:.c=.o)))
OBJECTS += $(addprefix $(BUILD)/,$(notdir $(ASM_SOURCES:.s=.o)))
vpath %.c $(sort $(dir $(C_SOURCES)))
vpath %.s $(sort $(dir $(ASM_SOURCES)))

all: $(BUILD)/$(TARGET).elf $(BUILD)/$(TARGET).hex $(BUILD)/$(TARGET).bin

$(BUILD)/%.o: %.c Makefile | $(BUILD)
	$(CC) -c $(CFLAGS) $< -o $@

$(BUILD)/%.o: %.s Makefile | $(BUILD)
	$(AS) -c $(ASFLAGS) $< -o $@

$(BUILD)/$(TARGET).elf: $(OBJECTS) Makefile
	$(CC) $(OBJECTS) $(LDFLAGS) -o $@
	$(SZ) $@

$(BUILD)/%.hex: $(BUILD)/%.elf
	$(CP) -O ihex $< $@

$(BUILD)/%.bin: $(BUILD)/%.elf
	$(CP) -O binary -S $< $@

$(BUILD):
	mkdir -p $@

flash: $(BUILD)/$(TARGET).elf
	$(PROGRAMMER) -c port=SWD -w $(BUILD)/$(TARGET).elf -v -rst

clean:
	rm -rf $(BUILD)

-include $(wildcard $(BUILD)/*.d)

.PHONY: all flash clean
