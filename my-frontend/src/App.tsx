//react imports
import React, {useState} from 'react';
import { useEffect } from 'react';
//css and assets
import './App.css';
import defaultProfile from './profile-icon-png-898.png';
import youtubelogo from './youtube_logo.png'
import spotifylogo from './spotify.png'
import googlelogo from './google.png'
//routes for navigation
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
//other pages
import Profile from './profile';
import Playlist from './playlist';

//it's a button, does button things
function MyButton() {
  return (
    <button className='my-button'>I'm feeling adventurous!</button>
  );
}

//dropdown form for logging in and registering 
function SignInDropdown({onClose, onLoginSuccess}: {onClose:()=>void; onLoginSuccess:(username:string)=> void}){
  //login form state
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  //registration form state
  const [showRegister, setShowRegister] = useState(false);
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regMessage, setRegMessage] = useState('');

  //handle login form submission
  const handleLogin = async (e:React.FormEvent)=>{
    e.preventDefault();
    console.log('Login form submitted'); 

    try{
      const response = await fetch('https://beattheblues.onrender.com/login',{ //fetching from backend
        method:'POST',
        headers:{
          'Content-Type':'application/json',
        },
        body:JSON.stringify({username,password}),
      });

      const data = await response.json();
      //console.log('Server response:', data);
      if(data.success){
        setMessage(`Welcome, ${data.username}!`);
        onLoginSuccess(data.username); 
      }
      else {
        setMessage(data.message);
      }
    }
    catch(error){
      console.error('Login error:', error);
      setMessage('An error occurred');
    }
  };

  //handle registration form submission
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch('https://beattheblues.onrender.com/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: regUsername,
          email: regEmail,
          password: regPassword,
        }),
      });
      const data = await response.json();
      setRegMessage(data.message);
    } catch (error) {
      console.error('Registration error:', error);
      setRegMessage('An error occurred');
    }
  };

  //rendering of login and registration form
  return(
    <div className="dropdown-menu">
      {showRegister ? (
        <>
          <form onSubmit={handleRegister}>
            <h3>Register</h3>
            <input
              type="text"
              placeholder="Username"
              value={regUsername}
              onChange={(e) => setRegUsername(e.target.value)}
            />
            <input
              type="email"
              placeholder="Email"
              value={regEmail}
              onChange={(e) => setRegEmail(e.target.value)}
            />
            <input
              type="password"
              placeholder="Password"
              value={regPassword}
              onChange={(e) => setRegPassword(e.target.value)}
            />
            <button type="submit">Sign Up</button>
            {regMessage && <p>{regMessage}</p>}
          </form>
          <p>
            Already have an account?{' '}
            <button onClick={() => setShowRegister(false)}>Sign In</button>
          </p>
        </>
      ) : (
        <>
          <form onSubmit={handleLogin}>
            <h3>Sign In</h3>
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="submit">Sign In</button>
            {message && <p>{message}</p>}
          </form>
          <p>
            Don't have an account?{' '}
            <button onClick={() => setShowRegister(true)}>Register</button>
          </p>
        </>
      )}
    </div>
  );
}

function App() {
  //UI state
  const [showDropDown, setShowDropDown] = useState(false);
  //login state
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState('');
  //search and recommendation state
  const [query, setQuery] = useState('');
  const [recommendation, setRecommendation] = useState('');

  //restore login state from local storage (helps to keep track of login status in other pages)
  useEffect(() => {
    const storedUsername = localStorage.getItem('username');
    if (storedUsername) {
      setIsLoggedIn(true);
      setUsername(storedUsername);
    }
  }, []);

  //send search query to backend for song reco
  const handleSearch = async () => {
    try {
      const response = await fetch('https://beattheblues-reco.onrender.com/recommend', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query })
      });
      const data = await response.json();
      setRecommendation(data.recommendation || 'No result');
    } catch (error) {
      console.error('Error fetching recommendation:', error);
      setRecommendation('Something went wrong.');
    }
  };
  //called for successful login
  const handleLoginSuccess = (user: string) => {
    setIsLoggedIn(true);
    setUsername(user);
    localStorage.setItem('username', user); 
  };
  //called for logout
  const handleLogout = () => {
    setIsLoggedIn(false);
    setUsername('');
    localStorage.removeItem('username'); // clear on logout
    setShowDropDown(false);
  };

  return (
    <Router> 
      <div className='top-bar'>
        <a
          href="#"
          className="top-link"
          onClick={(e) => {
            if (!isLoggedIn) {
              e.preventDefault();
              setShowDropDown(true);
            } else {
              window.location.href = '/playlist';
            }
          }}
        >
          Playlist
          </a>
        <a
          href="#"
          className="top-link"
          onClick={(e) => {
            if (!isLoggedIn) {
              e.preventDefault();
              setShowDropDown(true);
            } else {
              window.location.href = '/profile';
            }
          }}
        >
          Profile
        </a>
        <img
          src={defaultProfile}
          className='profile-icon'
          alt='Profile'
          onClick={() => setShowDropDown(prev => !prev)}
        />

        {showDropDown && !isLoggedIn && (
          <SignInDropdown
            onClose={() => setShowDropDown(false)}
            onLoginSuccess={handleLoginSuccess}
          />
        )}

        {showDropDown && isLoggedIn && (
          <div className='dropdown-menu'>
            <p>Welcome, {username}!</p>
            <button onClick={handleLogout}>Log out</button>
          </div>
        )}
      </div>

      <Routes>
        <Route path="/" element={
          <>
            <h1>beat the blues&#119070;</h1>
            <h2>What are you vibing to today?</h2>
            <div className='search-wrapper'>
              <input
                type="text"
                placeholder="Type a keyword, like an artist, genre, mood..."
                className="search-input"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                  handleSearch();
                  }
                }}
              />
            </div>
            <div className='button-wrapper'><MyButton /></div>
            {recommendation && (
              <div className="recommendation-result">
                <p>{recommendation}</p>
                {isLoggedIn && (
                  <button
                  onClick={async () => {
                    try {
                      const response = await fetch('https://beattheblues.onrender.com/playlist', {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                          username: username,
                          song: recommendation
                        })
                      });
                      const data = await response.json();
                      alert(data.message);
                    } catch (err) {
                      alert('Failed to save song');
                      console.error(err);
                    }
                  }}
                  >
                    Add to playlist
                    </button>
                  )}
                  
                  <div className="search-buttons">
                    <a
                    href={`https://www.youtube.com/results?search_query=${encodeURIComponent(recommendation)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    >
                      <img src={youtubelogo} alt="YouTube" className="search-icon" />
                    </a>
                    <a
                    href={`https://open.spotify.com/search/${encodeURIComponent(recommendation)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    >
                      <img src={spotifylogo} alt="Spotify" className="search-icon" />
                    </a>
                    <a
                    href={`https://www.google.com/search?q=${encodeURIComponent(recommendation)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    >
                      <img src={googlelogo} alt="Google" className="search-icon" />
                    </a>
                  </div>
                </div>
              )}
          </>
        } />
        <Route path="/profile" element={<Profile />} />
        <Route path="/playlist" element={<Playlist />} />
      </Routes>
    </Router>
  );
}


export default App;
