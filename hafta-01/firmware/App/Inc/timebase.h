/**
 * @file timebase.h
 * @brief 1 MHz, 32-bit, serbest çalışan zaman damgası (TIM2).
 *
 * - Tek 32-bit register okuması: ISR ve görevlerden güvenli, kilitsiz.
 * - Monoton; 2^32 us ~ 71,6 dakikada bir sarar.
 * - Farklar daima (uint32_t)(b - a) ile, yani mod 2^32 hesaplanır.
 */
#ifndef TIMEBASE_H
#define TIMEBASE_H

#include <stdint.h>
#include "stm32f4xx.h"

void timebase_init(void);

static inline uint32_t timer_us(void)
{
    return TIM2->CNT;
}

static inline uint32_t elapsed_us(uint32_t from, uint32_t to)
{
    return (uint32_t)(to - from); /* mod 2^32 */
}

#endif /* TIMEBASE_H */
