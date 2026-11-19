/*
 * Independent source-vs-monitor replay for original LPC_KIAS_0.
 *
 * Compiled only against C99 emitted from the source-qualified, explicitly
 * derived 047-assigned-control FRET→Ogma input. Does not modify original FRET.
 * One process per trace resets the Copilot historical-always state.
 */
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "monitor.h"

float kias = 0.0f;
static int actual_violations = 0;

void handlerLPC_KIAS_0(void) { actual_violations++; }

int main(int argc, char **argv) {
  if (argc != 2) return 10;
  const float cases[4][3] = {
    {10.0f, 0.0f, 3.0f},       /* exactly zero after a passing sample */
    {1.0f, -1.0f, 2.0f},       /* genuinely negative boundary control */
    {0.5f, 100.0f, 100.0f},   /* no boundary crossing, positive control */
    {0.0f, 0.0f, 0.0f},        /* source-entirely-valid zero trace */
  };
  char *end = NULL;
  const long which = strtol(argv[1], &end, 10);
  if (end == argv[1] || *end != '\0' || which < 0 || which > 3) return 11;

  int source_violations = 0;
  bool source_failed = false;
  int mismatching_steps = 0;
  for (int t = 0; t < 3; t++) {
    kias = cases[which][t];
    if (kias < 0.0f) source_failed = true;  /* source is H(kias >= 0.0) */
    if (source_failed) source_violations++;
    step();
    const bool same = actual_violations == source_violations;
    if (!same) mismatching_steps++;
    printf("case=%ld step=%d kias=%.3f source_violations=%d "
           "actual_violations=%d match=%s\n",
           which, t, (double)kias, source_violations, actual_violations,
           same ? "YES" : "NO");
  }
  printf("case=%ld observed-source-difference=%s mismatching_steps=%d\n",
         which, mismatching_steps ? "YES" : "NO", mismatching_steps);
  return 0;
}
