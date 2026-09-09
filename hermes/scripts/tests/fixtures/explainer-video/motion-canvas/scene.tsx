import {Circle, Img, Node, Rect, Txt, Video, makeScene2D} from '@motion-canvas/2d';
import {all, createRef, waitFor} from '@motion-canvas/core';
import {plan, copy, visible, mouthOpacity, time} from '@explainer/runtime';

export default makeScene2D(function* (view) {
  const portrait = plan.aspect === '9:16';
  const [width, height] = portrait ? [720, 1280] : [1280, 720];
  const character = plan.character;
  const presenter = createRef<Node>();
  const request = createRef<Circle>();
  const cache = createRef<Rect>();
  const span = portrait ? 190 : 230;
  view.fill('#101820');

  // Every approved row has its own key and reactive, half-open visibility window.
  view.add(plan.copy.map(row => (
    <Txt key={row.id} text={copy(row.id)} opacity={() => visible(row.id)}
      fontFamily={'Arial, "Hiragino Sans", sans-serif'} fill={'#ffffff'}
      fontSize={row.id === 'title' ? 52 : row.id === 'notice' ? 24 : 36}
      width={width - 80} textWrap textAlign={'center'}
      y={height * (row.id === 'title' ? -0.37 : row.id === 'notice' ? -0.28 : -0.17)} />
  )));
  view.add(
    <Node x={portrait || character.framing === 'none' ? 0 : -width * 0.14}>
      <Rect width={span * 2 + 100} height={6} fill={'#b6c9d8'} />
      <Rect ref={cache} width={110} height={120} radius={14}
        stroke={'#ffffff'} lineWidth={4} fill={'#273d50'} />
      <Circle ref={request} x={-span} size={48} fill={'#ffcf66'} />
    </Node>
  );
  if (character.framing !== 'none') {
    view.add(
      <Node ref={presenter} x={portrait ? 0 : width * 0.33} y={height * (portrait ? 0.27 : 0.12)}>
        {character.performance === 'animated' ? (
          <Video key={'character-body'} src={character.video} width={160} height={240}
            time={() => time()} loop={false} playbackRate={1} />
        ) : (
          <Img key={'character-body'} src={character.body} width={160} height={240} />
        )}
        {Object.entries(character.mouths).map(([shape, path]) => (
          <Img key={'character-mouth-' + shape} src={path} width={160} height={240}
            opacity={() => mouthOpacity(shape)} />
        ))}
      </Node>
    );
  }
  yield* request().x(0, 1.2);
  yield* waitFor(0.8);
  yield* all(cache().fill('#39786b', 0.6), request().scale(0.65, 0.6),
    character.performance === 'puppet' ? presenter().x(presenter().x() - 24, 0.6) : waitFor(0.6));
  yield* waitFor(1.4);
  yield* all(request().x(span, 1.2), request().scale(1, 1.2),
    character.performance === 'puppet' ? presenter().x(presenter().x() + 24, 1.2) : waitFor(1.2));
  yield* waitFor(0.8);
});
