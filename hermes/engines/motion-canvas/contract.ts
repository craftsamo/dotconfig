import {useScene2D} from '@motion-canvas/2d';
import plan from '@explainer/plan';
import cues from '@explainer/cues';

export {plan};
// Unlike generator-only useTime(), this signal is available during rendering
// and invalidates cached visibility/video bindings on every frame.
export function time(): number {
  return useScene2D().getView().globalTime();
}
export function copy(id: string): string {
  const row = plan.copy.find((item: any) => item.id === id);
  if (!row) throw new Error(`Unknown approved copy id: ${id}`);
  return row.text;
}
export function visible(id: string): number {
  const row = plan.copy.find((item: any) => item.id === id);
  if (!row) throw new Error(`Unknown approved copy id: ${id}`);
  const now = time();
  return Number(now >= row.start && now < row.end);
}
export function mouthOpacity(shape: string): number {
  if (!cues || !(shape in plan.character.mouths)) throw new Error('Unapproved mouth shape');
  const now = time() - cues.offset;
  const event = cues.events.find((item: any) => item.start <= now && now < item.end);
  return Number(shape === (event?.mouth ?? 'rest'));
}
