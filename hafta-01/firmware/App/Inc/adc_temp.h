/**
 * @file adc_temp.h
 * @brief Dahili sıcaklık sensörü ve VDDA (TEL içeriği). Bekleme yapmaz.
 */
#ifndef ADC_TEMP_H
#define ADC_TEMP_H

#include <stdint.h>

#define ADC_TEMP_INVALID  (-9999)

void     adc_temp_init(void);
void     adc_temp_step(void);     /* her TEL periyodunda bir kez: sonucu al, sonrakini başlat */
int32_t  adc_temp_dC(void);       /* 0,1 °C; geçersizse ADC_TEMP_INVALID */
uint32_t adc_vdda_mV(void);

#endif /* ADC_TEMP_H */
