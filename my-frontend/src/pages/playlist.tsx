import {useEffect, useState} from 'react';
import './playlist.css';

const Playlist = () => { 
  const username = localStorage.getItem('username'); 
  const [songs, set_songs] = useState<any[]>([]);
  const [loading, set_loading] = useState(true); //helps to track when data is still being loaded

  const fetch_playlist = async () => {
    try {
      const response = await fetch(`https://beattheblues.onrender.com/playlist?user=${username}`);
      const data = await response.json();
      set_songs(data);
    } 
    catch (err) {
      console.error(err);
    } 
    finally { //turns off the loading state, note that this is regardless of success or failure
      set_loading(false);
    }
  };

  const delete_song = async (id: number) => {
    try {
      await fetch(`https://beattheblues.onrender.com/playlist/${id}`, 
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
  }, [username]);

  if (!username) {
    return <p style={{textAlign: 'center'}}>Please log in to view your playlist and join the party!</p>;
  }

  let content;
  if (loading) {
    content = <p>Loading...</p>;
  } 
  else {
    if (songs.length === 0) {
      content = <p>No songs saved yet, try adding one!</p>;
    } 
    else {
      content = (
        <ul className='song-list'> {/*using unordered list here for songs, better than making a new line after every song*/}
          {songs.map(song => (
            <li key={song.id}> {/*key helps to identify each song with song id*/}
              🎵 {song.song}
              <button className='delete-button' onClick={() => delete_song(song.id)}>
                🗑 Delete
              </button>
            </li>
          ))}
        </ul>
      );
    }
  }

  return (
    <div>
      <div className = 'title-block'>
        <h3>Your Personal Playlist</h3>
        {content}
      </div>
      <a href="/" className="home-link">Return to Home</a>
    </div>
  );
};

export default Playlist;
