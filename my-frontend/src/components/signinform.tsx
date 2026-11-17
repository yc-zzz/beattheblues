import React, {useState} from 'react';
import {API_URL} from '../config';
import './signinform.css';
import {GoogleLogin} from '@react-oauth/google';

export default function SigninForm({when_closed, when_logged_in}: {when_closed: () => void; when_logged_in: (username: string) => void}) {
  const [username, set_user] = useState('');
  const [password, set_pass] = useState('');
  const [message, set_signin_message] = useState('');

  const [register_toggle, set_register_toggle] = useState(false);
  const [username_reg, set_username_reg] = useState('');
  const [email_reg, set_email_reg] = useState('');
  const [pass_reg, set_pass_reg] = useState('');
  const [message_reg, set_message_reg] = useState('');

  const login_handle = async(e:React.FormEvent)=>{
    e.preventDefault(); //apparently a good habit, used to stop refreshes when form submits
    try {
      const response = await fetch(`${API_URL}/login`, {//might take a few seconds if the backend is waking up
        method: 'POST',
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({username, password}),
      }); //sends user and pass as a jason object in a post request
      const data = await response.json();  //parse json response into js 
      if (data.success){
        set_signin_message(`Welcome, ${data.username}!`);
        when_logged_in(data.username);
      } 
      else {
        set_signin_message(data.message); //this is one of the error message from the backend, ie wrong password etc
      }
    } 
    catch (err) {
      console.error(err);
      set_signin_message('Error logging in, please try again');
    }
  };
  
  const reg_handle = async(e:React.FormEvent)=>{
    e.preventDefault();
    try {
      const response = await fetch(`${API_URL}/register`, {//same as login, might need to wait
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: username_reg, email: email_reg, password: pass_reg}),
      });
      const data = await response.json();
      set_message_reg(data.message); //can be success or failure message depending on the backend
    } 
    catch (err) {
      console.error(err);
      set_message_reg('Error with registration, please try again');
    }
  };

  let popup_form;
  if (register_toggle) { //simple switch mechanism for the form, clicking sign in sets it to false, vice versa for register
    popup_form = (
      <>
        <form className='auth-form' onSubmit={(e) => {
          e.preventDefault();
          const email_regex = /^[\w.-]+@([\w-]+\.)+[\w-]{2,}$/; //did all this just to realise browser already default check for email format lol
          if(!email_regex.test(email_reg)){
            set_message_reg("Invalid email format");
            return;
          }
          if(pass_reg.length <= 3){
            set_message_reg("Password must be at least 4 characters");
            return;
          }
          reg_handle(e);
        }}
        >
          <h2 className='auth-title'>Create an account</h2>
          {/* htmlFor + id link each label to its box: tapping the label focuses the box */}
          <div className='field'>
            <label htmlFor='reg-username'>Username</label>
            <input id='reg-username' type="text" autoComplete='username' value={username_reg} onChange={(e) => set_username_reg(e.target.value)} />
          </div>
          <div className='field'>
            <label htmlFor='reg-email'>Email</label>
            <input id='reg-email' type="email" autoComplete='email' value={email_reg} onChange={(e) => set_email_reg(e.target.value)} />
          </div>
          <div className='field'>
            <label htmlFor='reg-password'>Password</label>
            <input id='reg-password' type="password" autoComplete='new-password' value={pass_reg} onChange={(e) => set_pass_reg(e.target.value)} />
          </div>
          <button className='btn btn-primary' type="submit">Sign up</button>
          {message_reg && <p className='auth-message'>{message_reg}</p>}
        </form>
        <p className='auth-switch'>
          Already have an account?{' '}
          <button type='button' className='text-button' onClick={() => set_register_toggle(false)}>Sign in</button>
        </p>
      </>
    );
  } 
  else {
    popup_form = (
      <>
        <form className='auth-form' onSubmit={login_handle}>
          <h2 className='auth-title'>Sign in</h2>
          <div className='field'>
            <label htmlFor='login-username'>Username</label>
            <input id='login-username' type="text" autoComplete='username' value={username} onChange={(e) => set_user(e.target.value)} />
          </div>
          <div className='field'>
            <label htmlFor='login-password'>Password</label>
            <input id='login-password' type="password" autoComplete='current-password' value={password} onChange={(e) => set_pass(e.target.value)} />
          </div>
          <button className='btn btn-primary' type="submit">Sign in</button>
          {message && <p className='auth-message'>{message}</p>}
        </form>
        <div className='auth-divider'><span>or</span></div>
        <div className='auth-google'>
          <GoogleLogin 
          theme='filled_black'
          shape='pill'
          onSuccess={(response) => {
            fetch(`${API_URL}/auth/google`,{
              method:'POST',
              headers:{'Content-Type':'application/json'},
              body: JSON.stringify({token: response.credential}),
            })
            .then(response => response.json()) //parse the response jason
            .then(data => { //the parsed data
              if(data.success){
                when_logged_in(data.username);
              } else{
                console.error(data.message)
              }
            })
          }} 
          onError={() => console.error('Login failed')}
          />
        </div>
        <p className='auth-switch'>
          Don't have an account?{' '}
          <button type='button' className='text-button' onClick={() => set_register_toggle(true)}>Register</button>
        </p>
      </>
    );
  }

  return (
    <div className="dropdown-menu">
      <button type='button' className='auth-close' aria-label='Close' onClick={when_closed}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>
      </button>
      {popup_form}
    </div>
  );
}