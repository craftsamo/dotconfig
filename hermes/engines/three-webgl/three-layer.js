/* Hermes-owned synchronous Three.js layer. No independent animation clock. */
(() => {
  'use strict';
  let draw;
  const audit = {version: 1, time: null, draws: 0, errors: [], renderer: null};
  function fail(message) {
    audit.errors.push(String(message));
    console.error('HermesThree: ' + message);
    throw new Error('HermesThree: ' + message);
  }
  window.__hermesThreeAudit = audit;
  window.HermesThree = Object.freeze({
    mount({canvas, scene, camera, timeline, update}) {
      if (draw) fail('Only one Three canvas per standalone composition is supported');
      const root = document.querySelector('[data-composition-id]');
      const width = Number(root?.dataset.width), height = Number(root?.dataset.height);
      const duration = Number(root?.dataset.duration);
      if (!(canvas instanceof HTMLCanvasElement) || !root || !root.contains(canvas) ||
          root.dataset.hermesGraphics !== 'three-webgl2' ||
          !Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 ||
          width * height > 9000000 || !(duration > 0) ||
          !timeline || timeline !== window.__timelines?.[root.dataset.compositionId] ||
          typeof update !== 'function') fail('Invalid canvas/root/registered timeline/update contract');
      if (!window.THREE || THREE.REVISION !== '185') fail('Pinned Three.js r185 is required');
      let renderer;
      try {
        renderer = new THREE.WebGLRenderer({canvas, alpha: true, antialias: true, preserveDrawingBuffer: true});
      } catch (error) { fail('WebGL2 unavailable: ' + error.message); }
      const gl = renderer.getContext();
      if (!(gl instanceof WebGL2RenderingContext)) fail('WebGL2 context required');
      const debug = gl.getExtension('WEBGL_debug_renderer_info');
      audit.renderer = debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
      audit.width = width;
      audit.height = height;
      renderer.setPixelRatio(1);
      renderer.setSize(width, height, false);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.NoToneMapping;
      renderer.setClearColor(0x000000, 0);
      renderer.debug.onShaderError = () => fail('Shader compilation or linking failed');
      canvas.addEventListener('webglcontextlost', () => fail('WebGL context lost'));
      draw = time => {
        if (audit.errors.length) throw new Error('Three layer retained an earlier render error');
        if (!Number.isFinite(time)) fail('Seek time must be finite');
        const t = Math.max(0, Math.min(duration, time));
        try {
          // Suppressed GSAP callbacks cannot be the only place a canvas redraws.
          timeline.pause();
          timeline.totalTime(t, true);
          update(t);
          camera.updateProjectionMatrix();
          renderer.render(scene, camera);
          gl.finish();
          if (gl.getError() !== gl.NO_ERROR) fail('WebGL reported an error after render');
          audit.time = t;
          audit.draws += 1;
          audit.calls = renderer.info.render.calls;
          audit.programs = renderer.info.programs?.length || 0;
        } catch (error) {
          if (!audit.errors.length) fail(error.message);
          throw error;
        }
      };
      if (window.__hfThreeRender) fail('Another Three render hook already owns this page');
      window.__hfThreeRender = () => draw(window.__hfThreeTime ?? 0);
      window.addEventListener('hf-seek', event => draw(event.detail.time));
      draw(0);
      return renderer;
    }
  });
})();
