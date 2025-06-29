import React, { useState, useEffect } from 'react';
import './App.css';
import defaultprofile from './pics/profile-icon-png-898.png';
import youtubelogo from './pics/youtube_logo.png';
import spotifylogo from './pics/spotify.png';
import googlelogo from './pics/google.png';
import {BrowserRouter as Router, Routes, Route} from 'react-router-dom';
import SigninForm from './components/signinform';
import Profile from './pages/profile';
import Playlist from './pages/playlist';
//putting it here before I lose track
//h1: homepage logo h2: words below the log h3: first line in playlist and profile h5: register/login in the popup 

function MyButton({ onClick }:{onClick: () => void }) {
  return <button className='my-button' onClick={onClick}>I'm feeling adventurous!</button>;
}

function App() {
  const [popup, set_popup] = useState(false);
  const [logged_in, set_logged_in] = useState(false);
  const [username, set_user] = useState('');
  const [query, set_query] = useState('');
  const [recommendation, set_reco] = useState('');
  const [valid_reco, set_reco_validity] = useState(false)

  useEffect( () => {
    const stored_user = localStorage.getItem('username');
    if (stored_user) {
      set_logged_in(true);
      set_user(stored_user);
    }
  }, []);

  const search_handle = async() => {
    try {
      const response = await fetch('https://beattheblues-reco.onrender.com/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await response.json();
      set_reco(data.recommendation || 'No result, try another prompt?'); //sometimes first try lead to no result, will try to track down why
      set_reco_validity(!!data.recommendation); //TIL !! force it to become boolean, pretty cool
      if (data.recommendation == "Please give us a new description!"){
        set_reco_validity(false);
      }
    } 
    catch (err) {
      console.error(err);
      set_reco('Cannot fetch recommendation, try again later.');
    }
  };

  const login_success = (user: string)=>{
    set_logged_in(true);
    set_user(user);
    localStorage.setItem('username', user);
  };

  const logout_handle = ()=>{
    set_logged_in(false);
    set_user('');
    localStorage.removeItem('username');
    set_popup(false);
  };

  const playlist_add = async () => {
    try {
      const response = await fetch('https://beattheblues.onrender.com/playlist', {
        method: 'POST',
        headers: {'Content-Type': 'application/json' },
        body: JSON.stringify({username, song: recommendation})
      });
      const data = await response.json();
      alert(data.message);
    } 
    catch (err){
      alert('Failed to save song');
      console.error(err);
    }
  };

  let popup_content;
  if (popup && !logged_in) {
    popup_content = (
      <SigninForm
        when_closed={() => set_popup(false)}
        when_logged_in={login_success}
      />
    );
  } else if (popup && logged_in) {
    popup_content = (
      <div className='dropdown-menu'>
        <p>Welcome, {username}!</p>
        <button onClick={logout_handle}>Log out</button>
      </div>
    );
  }

  let reco_stuffs;
  if (recommendation) {
    reco_stuffs = (
      <div className="recommendation-result">
        <p>{recommendation}</p>
        {valid_reco && (
          <div>
            <div className="search-buttons">
              <a href={`https://www.youtube.com/results?search_query=${encodeURI(recommendation)}`} target="_blank" rel="noopener noreferrer">
              <img src={youtubelogo} alt="YouTube" className="search-icon" />
              </a>
              <a href={`https://open.spotify.com/search/${encodeURI(recommendation)}`} target="_blank" rel="noopener noreferrer">
              <img src={spotifylogo} alt="Spotify" className="search-icon" />
              </a>
              <a href={`https://www.google.com/search?q=${encodeURI(recommendation)}`} target="_blank" rel="noopener noreferrer">
              <img src={googlelogo} alt="Google" className="search-icon" />
              </a>
            </div>
            {logged_in && (
              <div className="add-button-wrapper">
                <button className='add-button' onClick={playlist_add}>Add to playlist</button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <Router>
      <div className='top-bar'>
        <a href="#" className="top-link" onClick={(e) => {
          if (!logged_in) {
            e.preventDefault();
            set_popup(true);
          } 
          else {
            window.location.href = '/playlist';
          }
        }}>Playlist</a>

        <a href="#" className="top-link" onClick={(e) => {
          if (!logged_in) {
            e.preventDefault();
            set_popup(true);
          } 
          else {
            window.location.href = '/profile';
          }
        }}>Profile</a>

        <img src={defaultprofile} className='profile-icon' alt='Profile' onClick={() => set_popup(prev => !prev)} />

        {popup_content}
      </div>

      <Routes>
        <Route path="/" element={
          <div className="home-page">
            <h1>beat the blues&#119070;</h1>
            <h2>What are you vibing to today?</h2>
            <div className='search-wrapper'>
              <input
                type="text"
                placeholder="Type a keyword, like an artist, genre, mood..."
                className="search-input"
                value={query}
                onChange={e => set_query(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') search_handle(); }}
              />
            </div>
            <div className='button-wrapper'>
              <MyButton onClick={() => {
                set_reco("This button is not implemented yet!😛");
                set_reco_validity(false);
                }} /> {/* will leave this for later, suppose to lead to a complete random song */}
            </div> 
            {reco_stuffs}
          </div>
        } />
        <Route path="/profile" element={<Profile />} />
        <Route path="/playlist" element={<Playlist />} />
      </Routes>
    </Router>
  );
}

export default App;
