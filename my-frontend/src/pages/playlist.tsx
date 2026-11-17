import {useCallback, useEffect, useState} from 'react';
import {API_URL} from '../config';
import './playlist.css';
import SongLinks from '../components/SongLinks';

const Playlist = () => { 
  const username = localStorage.getItem('username'); 
  const [songs, set_songs] = useState<any[]>([]);
  const [loading, set_loading] = useState(true); //helps to track when data is still being loaded

  // useCallback keeps the same function between renders (until username changes),
  // so listing it as a useEffect dependency does not refetch on every render.
  const fetch_playlist = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/playlist?user=${username}`);
      const data = await response.json();
      set_songs(data);
    } 
    catch (err) {
      console.error(err);
    } 
    finally { //turns off the loading state, note that this is regardless of success or failure
      set_loading(false);
    }
  }, [username]);

  const delete_song = async (id: number) => {
    try {
      await fetch(`${API_URL}/playlist/${id}`, 
      {
        method: 'DELETE',
      });
      set_songs(prev_songs => {
        const updated_songs = prev_songs.filter(song => song.id !== id); //creates a new array that filters out the song with the given id
        return updated_songs;
      });
    } 
    catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    if (username) {
      fetch_playlist(); //fetches the playlist as long as user is logged in
    } 
    else {
      set_loading(false);
    }
  }, [username, fetch_playlist]);

  if (!username) {
    return (
      <main className='page'>
        <p className='empty-state'>Please log in to view your playlist and join the party!</p>
      </main>
    );
  }

  let content;
  if (loading) {
    content = <p className='empty-state'>Loading...</p>;
  } 
  else {
    if (songs.length === 0) {
      content = <p className='empty-state'>No songs saved yet, try adding one!</p>;
    } 
    else {
      content = (
        <ul className='song-list'> {/*using unordered list here for songs, better than making a new line after every song*/}
          {songs.map(song => (
            <li key={song.id} className='card song-card'> {/*key helps to identify each song with song id*/}
              <div className='song-row'>
                <span className='song-name'>{song.song}</span>
                <button
                  type='button'
                  className='delete-button'
                  aria-label={`Remove ${song.song} from playlist`}
                  onClick={() => delete_song(song.id)}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"></path></svg>
                </button>
              </div>
              <SongLinks song={song.song} />
            </li>
          ))}
        </ul>
      );
    }
  }

  return (
    <main className='page'>
      <a href="/" className="back-link">← Back to home</a>
      <div className='page-heading'>
        <h1 className='page-title'>Your playlist</h1>
        {!loading && songs.length > 0 && (
          <p className='page-subtitle'>{songs.length} saved {songs.length === 1 ? 'song' : 'songs'}</p>
        )}
      </div>
      {content}
    </main>
  );
};

export default Playlist;