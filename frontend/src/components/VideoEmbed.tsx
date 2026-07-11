import type { ShowVideoCommand } from '../types';

interface Props {
  video: ShowVideoCommand;
}

export function VideoEmbed({ video }: Props) {
  return (
    <div className="video-embed">
      <iframe
        src={video.url}
        title={video.caption}
        className="video-embed__frame"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
      <p className="video-embed__caption">{video.caption}</p>
    </div>
  );
}
