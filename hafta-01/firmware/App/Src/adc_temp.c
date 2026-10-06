/**
 * @file adc_temp.c
 * @brief TEL içeriği için dahili sıcaklık sensörü ve VDDA (ADC1, kanal 16/17).
 *
 * Dönüşüm arka planda yürür: her telemetri periyodunda bir önceki sonuç okunur ve
 * sıradaki kanal başlatılır. TelemetryTask hiç beklemez (ölçülen yola ek CPU yükü yok).
 * Kalibrasyon: fabrika değerleri TS_CAL1 (30 °C), TS_CAL2 (110 °C), VREFINT_CAL (3,3 V).
 */
#include "adc_temp.h"
#include "stm32f4xx.h"

#define TS_CAL1      (*(const uint16_t *)0x1FFF7A2CUL)
#define TS_CAL2      (*(const uint16_t *)0x1FFF7A2EUL)
#define VREFINT_CAL  (*(const uint16_t *)0x1FFF7A2AUL)

#define CH_TEMP 16u
#define CH_VREF 17u

static uint32_t s_ch = CH_TEMP;
static uint32_t s_raw_t, s_raw_v;

static void start(uint32_t ch)
{
    ADC1->SQR3 = ch;
    ADC1->CR2 |= ADC_CR2_SWSTART;
}

void adc_temp_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_ADC1EN;
    (void)RCC->APB2ENR;
    ADC->CCR = (ADC->CCR & ~ADC_CCR_ADCPRE) | ADC_CCR_ADCPRE_0 | ADC_CCR_TSVREFE; /* 84/4 = 21 MHz */
    ADC1->CR1 = 0;                                  /* 12 bit */
    ADC1->SQR1 = 0;                                 /* 1 dönüşüm */
    ADC1->SMPR1 = (7u << ADC_SMPR1_SMP16_Pos) | (7u << ADC_SMPR1_SMP17_Pos); /* 480 çevrim */
    ADC1->CR2 = ADC_CR2_ADON;
    start(s_ch);
}

void adc_temp_step(void)
{
    if ((ADC1->SR & ADC_SR_EOC) == 0u) {
        return;                                     /* henüz bitmedi: sonraki periyot */
    }
    const uint32_t raw = ADC1->DR & 0xFFFu;         /* EOC'yi temizler */
    if (s_ch == CH_TEMP) {
        s_raw_t = raw;
        s_ch = CH_VREF;
    } else {
        s_raw_v = raw;
        s_ch = CH_TEMP;
    }
    start(s_ch);
}

int32_t adc_temp_dC(void)
{
    if (s_raw_t == 0u || s_raw_v == 0u || TS_CAL2 <= TS_CAL1) {
        return ADC_TEMP_INVALID;
    }
    /* Ham sıcaklık değerini 3,3 V referansına ölçekle (VDDA düzeltmesi) */
    const int32_t raw33 = (int32_t)((s_raw_t * (uint32_t)VREFINT_CAL) / s_raw_v);
    return 300 + ((raw33 - (int32_t)TS_CAL1) * 800) / ((int32_t)TS_CAL2 - (int32_t)TS_CAL1);
}

uint32_t adc_vdda_mV(void)
{
    return (s_raw_v == 0u) ? 0u : (3300u * (uint32_t)VREFINT_CAL) / s_raw_v;
}
