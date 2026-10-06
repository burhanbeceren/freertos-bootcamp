/**
 * @file inject.c
 * @brief Buton kesmesinin donanımla tetiklenmesi: EXTI enjeksiyonu ve EXTI testi.
 *
 * EXTI enjeksiyonu (SRC_INJ):
 *   TIM7 tek atımlık zamanlayıcısı 0,5–0,9 s arası rastgele aralıklarla kesme üretir.
 *   TIM7 ISR'ı EXTI->SWIER ile EXTI0 hattını yazılımla tetikler. Ölçülen yol (EXTI0
 *   ISR -> ButtonTask -> kuyruk -> UartTxTask -> TC) fiziksel basışla BİREBİR aynıdır;
 *   yalnızca uyarım insan eli yerine zamanlayıcıdan gelir. Rastgele aralık, basışların
 *   telemetri periyodunun her fazına düşmesini sağlar. Böylece aynı koşullar
 *   tekrarlanabilir biçimde, insan basmadan ölçülebilir.
 *
 * EXTI testi:
 *   Ölçüm dışındayken SWIER yazımından EXTI0 ISR'ın ilk ölçüm komutuna kadar geçen
 *   süreyi DWT çevrim sayacıyla ölçer (kesme giriş gecikmesi; t0'ın önündeki kısım).
 *
 * Görev değildir: 3 uygulama görevi kuralı korunur.
 */
#include "app.h"
#include "app_config.h"
#include "timebase.h"

#define BTN_EXTI_LINE  (1u << 0)

static volatile bool     s_inject_pending;   /* sonraki EXTI0 kenarı enjekte */
static volatile bool     s_test_active;      /* sonraki EXTI0 kenarı test    */
static volatile uint32_t s_test_isr_cyc;
static uint32_t          s_rng = 0x1234567u;

static uint32_t rnd(void)
{
    s_rng ^= s_rng << 13;
    s_rng ^= s_rng >> 17;
    s_rng ^= s_rng << 5;
    return s_rng;
}

/* TIM7: 10 kHz sayım, tek atım (OPM), yalnızca taşma UIF üretir (URS). */
static void arm_ms(uint32_t ms)
{
    TIM7->CR1 &= ~TIM_CR1_CEN;
    TIM7->CNT = 0;
    TIM7->ARR = (ms * 10u) - 1u;
    TIM7->EGR = TIM_EGR_UG;
    TIM7->SR = 0;
    TIM7->CR1 |= TIM_CR1_CEN;
}

void inject_init(void)
{
    __HAL_RCC_TIM7_CLK_ENABLE();
    uint32_t timclk = HAL_RCC_GetPCLK1Freq();
    if ((RCC->CFGR & RCC_CFGR_PPRE1) != RCC_CFGR_PPRE1_DIV1) {
        timclk *= 2u;
    }
    TIM7->CR1 = TIM_CR1_OPM | TIM_CR1_URS;
    TIM7->PSC = (timclk / 10000u) - 1u;        /* 84 MHz -> 10 kHz */
    TIM7->DIER = TIM_DIER_UIE;
    TIM7->SR = 0;
    /* EXTI0'dan (5) düşük öncelik: SWIER yazılınca EXTI0 hemen araya girer. */
    HAL_NVIC_SetPriority(TIM7_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(TIM7_IRQn);

    /* DWT çevrim sayacı (EXTI testi) */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    s_rng ^= timer_us();
}

void inject_start(void)
{
    s_inject_pending = false;
    if (g_source == SRC_INJ) {
        s_rng ^= timer_us();
        arm_ms(WARMUP_MS + 200u + (rnd() % INJ_SPAN_MS));
    }
}

void inject_stop(void)
{
    TIM7->CR1 &= ~TIM_CR1_CEN;
    TIM7->SR = 0;
    s_inject_pending = false;
}

void TIM7_IRQHandler(void)
{
    TIM7->SR = 0;
    if (g_source != SRC_INJ || !g_started || g_stop_pending) {
        return;                                   /* deney bitti: yeniden kurma */
    }
    s_inject_pending = true;
    EXTI->SWIER = BTN_EXTI_LINE;                  /* EXTI0 hemen araya girer */
    arm_ms(INJ_MIN_MS + (rnd() % INJ_SPAN_MS));
}

bool inject_take_pending(void)
{
    if (s_inject_pending) {
        s_inject_pending = false;
        return true;
    }
    return false;
}

bool exti_test_hook(void)
{
    if (s_test_active) {
        s_test_isr_cyc = DWT->CYCCNT;
        s_test_active = false;
        return true;
    }
    return false;
}

void exti_test_run(uint32_t n, uint32_t *mn, uint32_t *mean, uint32_t *mx)
{
    uint32_t lo = UINT32_MAX, hi = 0;
    uint64_t sum = 0;

    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;   /* hata ayıklayıcı kapatmış olabilir */
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    for (uint32_t i = 0; i < n; i++) {
        s_test_active = true;
        const uint32_t c0 = DWT->CYCCNT;
        EXTI->SWIER = BTN_EXTI_LINE;
        __DSB();
        __ISB();                                  /* ISR burada araya girer */
        for (uint32_t guard = 0; s_test_active && guard < 100000u; guard++) { }
        const uint32_t d = s_test_isr_cyc - c0;
        if (d < lo) lo = d;
        if (d > hi) hi = d;
        sum += d;
    }
    *mn = lo;
    *mx = hi;
    *mean = (uint32_t)(sum / (n ? n : 1u));
}
