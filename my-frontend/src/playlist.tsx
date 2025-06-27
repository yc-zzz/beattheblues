import React, { useEffect, useState } from 'react';
import './playlist.css';

const Playlist = () => {
  const username = localStorage.getItem('username');
  const [songs, setSongs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPlaylist = async () => {
    try {
      const response = await fetch(`https://beattheblues.onrender.com/playlist?user=${username}`);
      const data = await response.json();
      setSongs(data);
    } catch (error) {
      console.error('Error loading playlist:', error);
    } finally {
      setLoading(false);
    }
  };

  const removeSong = async (id: number) => {
    try {
      await fetch(`https://beattheblues.onrender.com/playlist/${id}`, {
        method: 'DELETE',
      });
      setSongs(prev => prev.filter(song => song.id !== id));
    } catch (error) {
      console.error('Failed to delete song:', error);
    }
  };

  useEffect(() => {
    if (username) {
      fetchPlaylist();
    } else {
      setLoading(false);
    }
  }, [username]);

  if (!username) {
    return <p style={{ textAlign: 'center' }}>Please log in to view your playlist.</p>;
  }

  return (
    <div style={{ textAlign: 'center', padding: '2rem' }}>
      <h2>Your Playlist</h2>
      {loading ? (
        <p>Loading...</p>
      ) : songs.length === 0 ? (
        <p>No songs saved yet!</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {songs.map(song => (
            <li key={song.id} style={{ marginBottom: '1rem' }}>
              🎵 {song.song}
              <button
                style={{
                  marginLeft: '1rem',
                  padding: '0.2rem 0.6rem',
                  borderRadius: '5px',
                  background: '#ff4d4d',
                  color: 'white',
                  border: 'none',
                  cursor: 'pointer',
                }}
                onClick={() => removeSong(song.id)}
              >
                🗑 Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default Playlist;
