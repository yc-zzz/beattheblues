import React from 'react';
import './playlist.css';

const Playlist = () => {
  const username = localStorage.getItem('username');

  return (
    <div>
      <h2>Welcome, {username ? username : 'Guest'}!</h2>
      {username ? 
      (<p>
        This is your playlist page.
        </p>) : 
      (<p>Please log in to view your playlist.</p>)}
    </div>
  );
};

export default Playlist;