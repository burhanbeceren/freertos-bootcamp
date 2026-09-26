/**
 * @file work.h
 * @brief S4/S5 için sabit iterasyonlu, optimizasyonla silinmeyen CPU işi.
 *
 * vTaskDelay() CPU yükü ÜRETMEZ; burada gerçekten komut yürütülür.
 * Kesmeler kapatılmaz.
 */
#ifndef WORK_H
#define WORK_H

#include <stdint.h>

/* Açılışta (scheduler öncesi) iterasyon/ms değerini ölçer. */
void     work_calibrate(void);
uint32_t work_iters_per_ms(void);
uint32_t work_iters_for_us(uint32_t us);

/* iters kez xorshift32 çalıştırır; sonuç TEL mesajında kullanılır (silinemez). */
uint32_t work_run(uint32_t iters);

#endif /* WORK_H */
