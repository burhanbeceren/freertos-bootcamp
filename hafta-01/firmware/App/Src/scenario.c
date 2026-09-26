/**
 * @file scenario.c
 */
#include "scenario.h"
#include <string.h>

static const scenario_t s_table[SCENARIO_COUNT] = {
    { "S0",   0u,    0u },   /* Telemetri kapalı, referans         */
    { "S1", 100u,    0u },   /* 10 Hz                              */
    { "S2",  20u,    0u },   /* 50 Hz                              */
    { "S3",  10u,    0u },   /* 100 Hz                             */
    { "S4",  10u, 2000u },   /* 100 Hz + ~2 ms CPU işi  (~%20 ek)  */
    { "S5",  10u, 5000u },   /* 100 Hz + ~5 ms CPU işi  (~%50 ek)  */
};

static const scenario_t *volatile s_current = &s_table[0];

const scenario_t *scenario_get(uint32_t idx)
{
    return (idx < SCENARIO_COUNT) ? &s_table[idx] : NULL;
}

const scenario_t *scenario_find(const char *name)
{
    for (uint32_t i = 0; i < SCENARIO_COUNT; i++) {
        if (strcmp(s_table[i].name, name) == 0) {
            return &s_table[i];
        }
    }
    return NULL;
}

const scenario_t *scenario_current(void)
{
    return s_current;
}

void scenario_set(const scenario_t *s)
{
    s_current = s;
}
