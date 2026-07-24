import { RotateCcw, SlidersHorizontal } from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  Button,
  Slider,
} from '@/components/ui';
import { useWeightStore } from '@/stores/weightStore';
import { CRITERIA, WEIGHT_PRESETS } from '@/lib/constants';

/**
 * WeightStudio — §12.6 (D6). Five sliders, one per criterion. Weights always
 * total 100 (adjusting one proportionally redistributes the rest). Moving a
 * slider re-ranks the list in real time. Simulation is NOT policy: a persistent
 * chip says so, and saving as policy lives at /admin/scoring-policy (sysadmin).
 */
export function WeightStudio({
  open,
  onOpenChange,
  summary,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  summary?: React.ReactNode;
}) {
  const { weights, simulated, setWeight, applyWeights, resetToPolicy } = useWeightStore();

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent width="md">
        <DrawerHeader>
          <DrawerTitle>Weight studio</DrawerTitle>
          <DrawerDescription>
            Explore how the ranking changes when the criteria are weighted differently. Changes here
            are a simulation — they are not saved as policy.
          </DrawerDescription>
        </DrawerHeader>

        <DrawerBody>
          <div className="flex flex-col gap-6">
            {/* Simulated banner */}
            {simulated && (
              <div className="flex items-center gap-2 rounded-sm border border-warning-border bg-warning-bg px-3 py-2" role="status">
                <span className="h-2 w-2 shrink-0 rounded-full bg-warning-fg" />
                <span className="font-mono text-label uppercase text-warning-fg">
                  Simulated weights — not saved
                </span>
              </div>
            )}

            {/* Presets */}
            <div className="flex flex-col gap-2">
              <span className="font-mono text-label uppercase text-text-muted">Presets</span>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {WEIGHT_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyWeights(preset.weights)}
                    className="flex flex-col gap-0.5 rounded-sm border border-hairline bg-surface p-3 text-left transition-colors hover:border-strong hover:bg-surface-sunken focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                  >
                    <span className="text-body-sm font-semibold text-ink">{preset.label}</span>
                    <span className="text-label text-text-muted">{preset.description}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Sliders */}
            <div className="flex flex-col gap-5">
              {CRITERIA.map((c) => (
                <div key={c.key} className="flex flex-col gap-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <label className="text-body font-semibold text-ink" htmlFor={`weight-${c.key}`}>
                      {c.label}
                    </label>
                    <span className="font-mono text-data-lg tabular-nums text-ink">{weights[c.key]}</span>
                  </div>
                  <p className="text-body-sm text-text-muted">{c.description}</p>
                  <Slider
                    id={`weight-${c.key}`}
                    value={[weights[c.key]]}
                    onValueChange={([v]) => setWeight(c.key, v ?? 0)}
                    min={0}
                    max={100}
                    step={1}
                    aria-label={`${c.label} weight`}
                  />
                </div>
              ))}
            </div>

            {/* Total */}
            <div className="flex items-center justify-between rounded-sm border border-hairline bg-surface-sunken px-3 py-2">
              <span className="font-mono text-label uppercase text-text-muted">Total</span>
              <span className="font-mono text-data-lg font-semibold tabular-nums text-ink">100</span>
            </div>

            {/* Consequence summary */}
            {summary && (
              <div className="rounded-md border border-info-border bg-info-bg p-3 text-body-sm text-info-fg" aria-live="polite">
                {summary}
              </div>
            )}
          </div>
        </DrawerBody>

        <DrawerFooter className={cn('justify-between')}>
          <Button
            variant="ghost"
            onClick={resetToPolicy}
            disabled={!simulated}
            icon={<RotateCcw size={16} className="shrink-0" />}
          >
            Reset to policy
          </Button>
          <Button variant="secondary" onClick={() => onOpenChange(false)} icon={<SlidersHorizontal size={16} className="shrink-0" />}>
            Done
          </Button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
