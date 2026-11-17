import React, {useState, useEffect} from 'react';
import {API_URL, RECO_API_URL} from './config';
import './App.css';
import {BrowserRouter as Router, Routes, Route} from 'react-router-dom';
import SigninForm from './components/signinform';
import SongLinks from './components/SongLinks';
import Profile from './pages/profile';
import Playlist from './pages/playlist';
import '../node_modules/react-tooltip/dist/react-tooltip.css'
import {Tooltip} from 'react-tooltip'
//putting it here before I lose track
//h1: page title on each page, h2: section headings, h3: song title in the result card

function MyButton({onClick, disabled}:{onClick: () => void; disabled: boolean}) {
  return <button 
  type='button'
  className='btn random-button' 
  onClick={onClick}
  disabled={disabled}
  data-tooltip-id="my-tooltip"
  data-tooltip-content="Get a completely random song!"
  data-tooltip-place="bottom">
    Surprise me with a random song
    </button>;    
}

// Splits "Title by Artist" into its two parts, so the card can show them on
// separate lines. Uses the LAST " by " in case the title itself contains one.
function split_song(song: string) {
  const by_index = song.lastIndexOf(' by ');
  if (by_index <= 0) {
    return {title: song, artist: ''};
  }
  return {title: song.slice(0, by_index), artist: song.slice(by_index + 4)};
}

function App() {
  const [popup, set_popup] = useState(false); //basically login tab
  const [menu_open, set_menu_open] = useState(false); //the nav menu on phones
  const [logged_in, set_logged_in] = useState(false);
  const [username, set_user] = useState('');
  const [query, set_query] = useState('');
  const [recommendation, set_reco] = useState('');
  const [valid_reco, set_reco_validity] = useState(false); //this is added later to control when the search icons show up
  const [search_mode, set_search_mode] = useState(false); //alternate search mode between recomm and search
  const [is_loading, set_loading] = useState(false); //true while waiting for the backend

  useEffect( () => {
    const stored_user = localStorage.getItem('username');
    if (stored_user) {
      set_logged_in(true);
      set_user(stored_user);
    }
  }, []);

  const search_handle = async() => {
    let url = '';
    const payload = {query};

    if (search_mode){ //altermnate netween the two search mode
      url = `${RECO_API_URL}/search`;
    } else {
      url = `${RECO_API_URL}/recommend`;
    }

    set_loading(true);
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      let result = '';
      
      if (search_mode && data["search result"]) {
        result = data["search result"];
      } else if (!search_mode && data["recommendation"]) {
        result = data["recommendation"];
      }
      set_reco(result || 'No result, try another prompt?'); 

      if (result === "Please give us a new description!" || result === "Please try a different song."){
        set_reco_validity(false);
      } else{
          set_reco_validity(!!result);
      }
    } catch (err) {
      console.error(err);
      set_reco('Cannot fetch recommendation, try again later.');
      set_reco_validity(false);
    } finally {
      set_loading(false);
    }
  };

  const random_handle = async() => {
    set_loading(true);
    try{
      const response = await fetch(`${API_URL}/random`);
      const data = await response.json();
      set_reco(data.recommendation);
      set_reco_validity(true);
    } catch(e){
      console.error(e);
      set_reco("Error fetching random song right now");
      set_reco_validity(false);
    } finally {
      set_loading(false);
    }
  };

  const switch_mode = (to_search: boolean) => {
    set_search_mode(to_search);
    set_reco('');
    set_reco_validity(false);
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
      const response = await fetch(`${API_URL}/playlist`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
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

  // Playlist and Personality need an account: if logged out, stop the link and open the sign-in popup instead
  const guard_link = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (!logged_in) {
      e.preventDefault(); //good habit to prevent accidental refreshe
      set_menu_open(false);
      set_popup(true);
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
        <p className='dropdown-welcome'>Welcome, {username}!</p>
        <button type='button' className='btn btn-outline' onClick={logout_handle}>Log out</button>
      </div>
    );
  }

  let reco_stuffs;
  if (is_loading) {
    reco_stuffs = <p className='reco-message'>Finding something for you...</p>;
  } else if (recommendation && valid_reco) { //when recommendation is legit, show the full card
    const {title, artist} = split_song(recommendation);
    reco_stuffs = (
      <section className='card reco-card' aria-label='Recommendation'>
        <div className='reco-header'>
          <div className='reco-art' aria-hidden='true'>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18V5l11-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="17" cy="16" r="3"></circle></svg>
          </div>
          <div className='reco-text'>
            <span className='reco-label'>Your recommendation</span>
            <h3 className='reco-title'>{title}</h3>
            {artist && <span className='reco-artist'>by {artist}</span>}
          </div>
        </div>
        <SongLinks song={recommendation} />
        {logged_in && (
          <button type='button' className='btn btn-primary' onClick={playlist_add}>+ Add to playlist</button>
        )}
      </section>
    );
  } else if (recommendation) { //an error or "try again" message: plain text, no card
    reco_stuffs = <p className='reco-message'>{recommendation}</p>;
  }

  let placeholder = "";
  if (search_mode){
    placeholder = "Search for a song or an artist...";
  } else {
    placeholder = "A genre, a mood, the weather..."
  }

  return (
    <Router>
      <header className='site-header'>
        <a href="/" className='brand'>beat the blues&#119070;</a>

        {/* Only visible on small screens (see App.css): opens and closes the nav */}
        <button
          type='button'
          className='menu-toggle'
          aria-label={menu_open ? 'Close menu' : 'Open menu'}
          aria-expanded={menu_open}
          onClick={() => set_menu_open(prev => !prev)}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"></path></svg>
        </button>

        <nav className={menu_open ? 'site-nav open' : 'site-nav'}>
          <a href="/playlist" className="nav-link" onClick={guard_link}>Playlist</a>
          <a href="/profile" className="nav-link" onClick={guard_link}>Personality</a>
          <button type='button' className='btn btn-outline' onClick={() => {
            set_menu_open(false);
            set_popup(prev => !prev);
          }}>
            {logged_in ? username : 'Sign in'}
          </button>
        </nav>
        {popup_content}
      </header>

      <Routes>
        <Route path="/" element={
          <main className="page home-page">
            <p className='eyebrow'>Music you haven't heard yet</p>
            <h1 className='hero-title'>What are you vibing to today?</h1>

            {/* Two buttons acting as one switch. aria-pressed tells screen readers which one is on. */}
            <div className='mode-toggle' role='group' aria-label='Mode'>
              <button type='button' aria-pressed={!search_mode} onClick={() => switch_mode(false)}>
                Discover obscure
              </button>
              <button type='button' aria-pressed={search_mode} onClick={() => switch_mode(true)}>
                Search exact song
              </button>
            </div>

            {/* A real <form>: pressing Enter or tapping the button both submit it */}
            <form className='search-bar' onSubmit={e => {
              e.preventDefault();
              search_handle();
            }}>
              <label htmlFor='search-input' className='visually-hidden'>Search</label>
              <input
                id='search-input'
                type="text"
                placeholder={placeholder}
                className="search-input"
                value={query}
                onChange={e => set_query(e.target.value)}
              /> 
              <button type='submit' className='search-submit' aria-label='Search' disabled={is_loading}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>
              </button>
            </form>

            <MyButton onClick={random_handle} disabled={is_loading} />

            {reco_stuffs}
          </main>
        } />
        <Route path="/profile" element={<Profile />} />
        <Route path="/playlist" element={<Playlist />} />
      </Routes>

      <footer className='site-footer'>beat the blues&#119070; · obscure songs, recommended</footer>
      <Tooltip id="my-tooltip" />
    </Router>
  );
}



export default App;