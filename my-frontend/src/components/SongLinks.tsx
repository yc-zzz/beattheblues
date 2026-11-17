import './SongLinks.css';

// The row of "find this song on..." buttons. It used to be copied into three
// files (home, playlist, personality); now each page just writes
// <SongLinks song="Title by Artist" />.
export default function SongLinks({song}: {song: string}) {
  const query = encodeURIComponent(song);
  // Spotify's search works better with just "Title Artist", without "by".
  const spotify_query = encodeURIComponent(song.replace(' by ', ' '));

  return (
    <div className="song-links">
      <a
        className="song-link"
        href={`https://www.youtube.com/results?search_query=${query}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        YouTube
      </a>
      <a
        className="song-link"
        href={`https://open.spotify.com/search/${spotify_query}`}
        target="_blank"
        rel="noopener noreferrer"
        data-tooltip-id="my-tooltip"
        data-tooltip-content="Spotify availability is subject to artist!"
        data-tooltip-place="bottom"
      >
        Spotify
      </a>
      <a
        className="song-link"
        href={`https://www.google.com/search?q=${query}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        Google
      </a>
    </div>
  );
}