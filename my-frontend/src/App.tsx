import React, {useState} from 'react';
import './App.css';
import defaultProfile from './profile-icon-png-898.png';

function MyButton() {
  return (
    <button className='my-button'>I'm feeling adventurous!</button>
  );
}

function SignInDropdown({onClose, onLoginSuccess}: {onClose:()=>void; onLoginSuccess:(username:string)=> void}){
  const [showRegister, setShowRegister] = useState(false);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regMessage, setRegMessage] = useState('');

  const handleLogin = async (e:React.FormEvent)=>{
    e.preventDefault();
    console.log('Login form submitted'); 
    
    try{
      const response = await fetch('http://localhost:5000/login',{
        method:'POST',
        headers:{
          'Content-Type':'application/json',
        },
        body:JSON.stringify({username,password}),
      });

      const data = await response.json();
      console.log('Server response:', data);

      if(data.success){
        setMessage(`Welcome, ${data.username}!`);
        onLoginSuccess(data.username);
        //onClose();
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

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch('http://localhost:5000/register', {
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

function RegisterForm() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const response = await fetch('http://localhost:5000/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      });

      const data = await response.json();
      setMessage(data.message);
    } catch (error) {
      console.error('Registration error:', error);
      setMessage('Something went wrong.');
    }
  };

  return (
    <div className="dropdown-menu">
      <form onSubmit={handleRegister}>
        <h3>Register</h3>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={e => setUsername(e.target.value)}
        />
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
        />
        <button type="submit">Sign Up</button>
        {message && <p>{message}</p>}
      </form>
    </div>
  );
}

function App() {

  const [showDropDown, setShowDropDown] = React.useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState('');

  const handleLoginSuccess = (user:string)=>{
    setIsLoggedIn(true);
    setUsername(user);
  };
  const handleLogout = ()=> {
    setIsLoggedIn(false);
    setUsername('');
    setShowDropDown(false);
  };

  return (
    <div>
      <div className='top-bar'>
        <a href="#" className='top-link'> Playlist </a>
        <a href="#" className='top-link'> Profile </a>
        <img 
          src={defaultProfile}
          className='profile-icon'
          alt='Profile'
          onClick={()=>setShowDropDown(prev=>!prev)}
        />

        {showDropDown && !isLoggedIn && (
          <SignInDropdown 
          onClose={()=>setShowDropDown(false)}
          onLoginSuccess={handleLoginSuccess}/>
        )}

        {showDropDown && isLoggedIn && (
          <div className='dropdown-menu'>
            <p>Welcome, {username}!</p>
            <button onClick={handleLogout}>Log out</button>
          </div>
        )}
      </div>
      
      <h1>beat the blues&#119070;</h1>
      <h2>What are you vibing to today?</h2>
      <div className='search-wrapper'>
        <input type = 'text' placeholder='Type a keyword, like an artist, genre, mood...' className='search-input'/>
      </div>
      <div className='button-wrapper'><MyButton /></div>
    </div>
  );
}

export default App;
