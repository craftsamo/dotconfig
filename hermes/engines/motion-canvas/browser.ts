// Pinned Motion Canvas 3.17.2 bootstrap, independent of Vite/editor/HMR.
import {bootstrap, MetaField, MetaFile, Renderer, RendererResult, ValueDispatcher, Vector2} from '@motion-canvas/core';
import {Img, Txt, Video} from '@motion-canvas/2d';
import scene from '@explainer/scene';
import meta from '@explainer/meta';
import job from '@explainer/job';
import {plan} from './contract';
import cues from '@explainer/cues';

declare global {
  interface Window {
    startRender: () => Promise<any>;
    pipelineFrame: (frame: number, data: string | null, audit: any) => Promise<void>;
    abortRender: () => void;
  }
}

function ensure(ok: unknown, message: string): asserts ok {
  if (!ok) throw new Error(message);
}
const normalize = (value: string) => value.replace(/\s+/g, ' ').trim();
const sampleFrames = new Set<number>(job.samples);
const assetPath = (value: string) => {
  const url = new URL(value, location.href);
  ensure(url.origin === location.origin, 'Remote media is forbidden');
  const name = decodeURIComponent(url.pathname.slice(1));
  ensure(name in plan.assets, `Unapproved media: ${name}`);
  return name;
};

function auditFrame(renderer: Renderer, frame: number) {
  const current: any = renderer.playback.currentScene;
  const time = frame / job.fps;
  return current.execute(() => {
    const view = current.getView();
    const texts = view.findAll((node: any) => node instanceof Txt && !(node.parent() instanceof Txt));
    const declared = new Map(plan.copy.map((row: any) => [row.id, row]));
    let checked = 0;
    for (const node of texts) {
      if (node.absoluteOpacity() < 0.01 || !node.text().trim()) continue;
      const row: any = declared.get(node.key);
      ensure(row && normalize(node.text()) === normalize(row.text), `Unapproved visible text: ${node.key}`);
      ensure(time >= row.start - 1e-7 && time < row.end + 1e-7, `Copy outside approved window: ${row.id}`);
    }
    if (sampleFrames.has(frame)) {
      for (const row of plan.copy) {
        if (!(row.start <= time && time < row.end)) continue;
        const node = current.getNode(row.id);
        ensure(node instanceof Txt && node.absoluteOpacity() > 0.01, `Missing visible copy: ${row.id}`);
        ensure(normalize(node.text()) === normalize(row.text), `Copy mismatch: ${row.id}`);
        const corners = node.cacheBBox().transformCorners(node.localToWorld());
        ensure(corners.every((p: any) => Number.isFinite(p.x) && Number.isFinite(p.y)
          && p.x >= -1 && p.y >= -1 && p.x <= job.width + 1 && p.y <= job.height + 1), `Copy outside canvas: ${row.id}`);
        checked++;
      }
    }
    for (const node of view.findAll((node: any) => node instanceof Img || node instanceof Video)) {
      assetPath(node.src());
      if (node instanceof Video) ensure(node.key === 'character-body', 'Only the approved character video is supported');
    }
    const character = plan.character;
    if (character.framing !== 'none') {
      const body = current.getNode('character-body');
      const animated = character.performance === 'animated';
      ensure(animated ? body instanceof Video : body instanceof Img, 'Missing character-body node');
      ensure(assetPath(body.src()) === (animated ? character.video : character.body), 'Character source changed');
      if (animated) {
        ensure(!body.loop() && body.playbackRate() === 1 && Math.abs(body.getCurrentTime() - time) < 1 / job.fps + 1e-6,
          'Character video timing changed');
      }
    } else {
      ensure(!current.getNode('character-body'), 'No-character mode gained a presenter');
    }
    let mouth = null;
    if (character.lip_sync === 'cues') {
      const local = time - cues.offset;
      mouth = cues.events.find((event: any) => event.start <= local && local < event.end)?.mouth ?? 'rest';
      for (const [shape, path] of Object.entries(character.mouths)) {
        const node = current.getNode('character-mouth-' + shape);
        ensure(node instanceof Img && assetPath(node.src()) === path, 'Missing mouth image');
        ensure(Math.abs(node.opacity() - Number(shape === mouth)) < 1e-6, `Mouth state mismatch at ${time}`);
      }
    }
    return {frame, time, copyChecked: checked, mouth};
  });
}

window.startRender = async () => {
  // makeScene2D's default metadata seed is random; always attach frozen metadata.
  (scene as any).name = 'explainer';
  const sceneMeta = new MetaFile('explainer');
  sceneMeta.loadData(meta);
  sceneMeta.attach(scene.meta);
  (scene as any).onReplaced = new ValueDispatcher(scene.config);
  let renderer: Renderer;
  class Exporter {
    static id = 'hermes/canvas-frames';
    static displayName = 'Hermes canvas frames';
    static meta() { return new MetaField('Hermes canvas frames', null); }
    static async create() { return new Exporter(); }
    async handleFrame(canvas: HTMLCanvasElement, frame: number, _sceneFrame: number, _name: string, signal: AbortSignal) {
      if (signal.aborted) throw new Error('Render aborted');
      const audit = auditFrame(renderer, frame);
      const write = job.mode === 'render' || sampleFrames.has(frame);
      await window.pipelineFrame(frame, write ? canvas.toDataURL('image/png') : null, audit);
    }
  }
  const project = bootstrap('explainer', {core: '3.17.2', two: '3.17.2', ui: null, vitePlugin: null},
    [{name: 'hermes/canvas-frames', exporters: () => [Exporter]}], {scenes: [scene]},
    new MetaFile('project'), new MetaFile('settings'));
  const errors: string[] = [];
  project.logger.onLogged.subscribe((entry: any) => {
    if (entry.level === 'error') errors.push(entry.message);
  });
  renderer = new Renderer(project);
  window.abortRender = () => renderer.abort();
  let result: number | undefined;
  renderer.onFinished.subscribe(value => { result = value; });
  // secondsToFrames uses ceil: stay inside the last-frame interval to avoid
  // a floating-point division/multiplication rounding up to one extra frame.
  await renderer.render({name: 'explainer', fps: job.fps, range: [0, (job.count - 1.25) / job.fps],
    size: new Vector2(job.width, job.height), resolutionScale: 1, colorSpace: 'srgb', background: '#101820',
    exporter: {name: Exporter.id, options: null}});
  ensure(result === RendererResult.Success && errors.length === 0, JSON.stringify({result, errors}));
  return {ok: true, errors};
};
