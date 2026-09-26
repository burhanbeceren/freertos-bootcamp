/**
 * @file scenario.h
 * @brief Altı zorunlu senaryo: önce telemetri frekansı, sonra CPU yükü değişir.
 */
#ifndef SCENARIO_H
#define SCENARIO_H

#include <stdint.h>

typedef struct {
    const char *name;         /* "S0".."S5"                               */
    uint32_t    period_ms;    /* 0 => telemetri kapalı (görev bloklu)      */
    uint32_t    work_us;      /* TelemetryTask'taki ek hesaplama (her periyot) */
} scenario_t;

#define SCENARIO_COUNT 6u

const scenario_t *scenario_get(uint32_t idx);
const scenario_t *scenario_find(const char *name);   /* NULL: bilinmeyen */
const scenario_t *scenario_current(void);
const scenario_t *scenario_next(void);                /* sıradaki senaryo (S5 -> S0) */
void              scenario_set(const scenario_t *s);

#endif /* SCENARIO_H */
