/**
 * @file timebase.c
 * @brief TIM2'yi 1 MHz serbest sayaç olarak kurar (HAL TIM modülü gerekmez).
 */
#include "timebase.h"
#include "stm32f4xx_hal.h"

void timebase_init(void)
{
    __HAL_RCC_TIM2_CLK_ENABLE();

    /* APB1 prescaler 1 değilse timer saati PCLK1 x 2'dir (RM0090 §7.2). */
    uint32_t timclk = HAL_RCC_GetPCLK1Freq();
    if ((RCC->CFGR & RCC_CFGR_PPRE1) != RCC_CFGR_PPRE1_DIV1) {
        timclk *= 2u;
    }

    TIM2->CR1 = 0;
    TIM2->PSC = (timclk / 1000000u) - 1u;   /* 84 MHz / 84 = 1 MHz */
    TIM2->ARR = 0xFFFFFFFFu;
    TIM2->CNT = 0;
    TIM2->EGR = TIM_EGR_UG;                  /* PSC'yi hemen yükle */
    TIM2->SR  = 0;
    TIM2->CR1 = TIM_CR1_CEN;

    /* Debugger durdurduğunda sayaç da dursun: adım adım izlemede tutarlılık. */
    DBGMCU->APB1FZ |= DBGMCU_APB1_FZ_DBG_TIM2_STOP;
}
