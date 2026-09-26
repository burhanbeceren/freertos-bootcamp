/**
 * @file stm32f4xx_it.c
 * @brief Çekirdek istisnaları ve SysTick.
 *
 * Ölçüm yolundaki kesmeler (EXTI0, USART2, DMA1_Stream6) App/ altında tanımlıdır.
 * SVC_Handler / PendSV_Handler FreeRTOSConfig.h eşlemesiyle port.c'den gelir.
 */
#include "main.h"
#include "FreeRTOS.h"
#include "task.h"

extern void xPortSysTickHandler(void);

static void fault_led(void)
{
    __disable_irq();
    LED_PORT->BSRR = LED_RED_PIN;
    for (;;) { }
}

void NMI_Handler(void)        { fault_led(); }
void HardFault_Handler(void)  { fault_led(); }
void MemManage_Handler(void)  { fault_led(); }
void BusFault_Handler(void)   { fault_led(); }
void UsageFault_Handler(void) { fault_led(); }
void DebugMon_Handler(void)   { }

/* SysTick: HAL tick (1 kHz) + FreeRTOS tick (configTICK_RATE_HZ = 1000). */
void SysTick_Handler(void)
{
    HAL_IncTick();
    if (xTaskGetSchedulerState() != taskSCHEDULER_NOT_STARTED) {
        xPortSysTickHandler();
    }
}
