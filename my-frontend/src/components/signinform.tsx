import React, {useState} from 'react';
import './signinform.css';
import {GoogleLogin} from '@react-oauth/google';
import profilepng from '../pics/person.png'
import emailpng from '../pics/email.png'
import passpng from '../pics/password.png'

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
      const response = await fetch('https://beattheblues.onrender.com/login', {//might take up to 50 seconds for render to respond cuz of free web service
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
      const response = await fetch('https://beattheblues.onrender.com/register', {//same as login, might need to wait
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
      <div>
        <form onSubmit={(e) => {
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
          <h5>Register</h5> 
          <div className='input'>
            <img src={profilepng} alt=""/>
            <input type="text" placeholder="Username" value={username_reg} onChange={(e) => set_username_reg(e.target.value)} /> 
          </div>
          <div className='input'>
            <img src={emailpng} alt=""/>
            <input type="email" placeholder="Email" value={email_reg} onChange={(e) => set_email_reg(e.target.value)} />
          </div>
          <div className='input'>
            <img src={passpng} alt=""/>
            <input type="password" placeholder="Password" value={pass_reg} onChange={(e) => set_pass_reg(e.target.value)} />
          </div>
          <button className='login-button' type="submit">Sign Up</button>
          {message_reg && <p>{message_reg}</p>}
        </form>
        <p>Already have an account? <button className='login-button' onClick={() => set_register_toggle(false)}>Sign In</button></p>
      </div>
    );
  } 
  else {
    popup_form = (
      <div>
        <form onSubmit={login_handle}>
          <h5>Sign In</h5>
          <div className='input'>
            <img src={profilepng} alt=""/>
            <input type="text" placeholder="Username" value={username} onChange={(e) => set_user(e.target.value)} />
          </div>
          <div className='input'>
            <img src={passpng} alt=""/>
            <input type="password" placeholder="Password" value={password} onChange={(e) => set_pass(e.target.value)} />
          </div>
          <button className='login-button' type="submit">Sign In</button>
          {message && <p>{message}</p>}
        </form>
        <GoogleLogin 
        onSuccess={(response) => {
          fetch('https://beattheblues.onrender.com/auth/google',{
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
        <p className='this-is-just-for-this-one-margin'>Don't have an account? <button className='login-button' onClick={() => set_register_toggle(true)}>Register</button></p>
      </div>
    );
  }

  return <div className="dropdown-menu">{popup_form}</div>;
}