/**
 * @file main.h
 */
#ifndef MAIN_H
#define MAIN_H

#include "stm32f4xx_hal.h"

/* STM32F407G-DISC1 LED'leri (PD12..PD15) */
#define LED_GREEN_PIN   GPIO_PIN_12   /* heartbeat değil: açılış tamam */
#define LED_ORANGE_PIN  GPIO_PIN_13   /* ölçüm aktif (START..STOP)     */
#define LED_RED_PIN     GPIO_PIN_14   /* hata: assert / fault / overflow */
#define LED_BLUE_PIN    GPIO_PIN_15   /* buton yanıtı (ButtonTask toggle) */
#define LED_PORT        GPIOD

void Error_Handler(void);

#endif /* MAIN_H */
