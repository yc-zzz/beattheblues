import React, {useState} from 'react';
import './signinform.css';

export default function SigninForm({ when_closed, when_logged_in }: { when_closed: () => void; when_logged_in: (username: string) => void }) {
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
        <form onSubmit={reg_handle}>
          <h5>Register</h5> 
          {/*onChange will be used in the future for checking email validity or length of password, not used rn*/}
          <input type="text" placeholder="Username" value={username_reg} onChange={(e) => set_username_reg(e.target.value)} /> 
          <input type="email" placeholder="Email" value={email_reg} onChange={(e) => set_email_reg(e.target.value)} />
          <input type="password" placeholder="Password" value={pass_reg} onChange={(e) => set_pass_reg(e.target.value)} />
          <button type="submit">Sign Up</button>
          {message_reg && <p>{message_reg}</p>}
        </form>
        <p>Already have an account? <button onClick={() => set_register_toggle(false)}>Sign In</button></p>
      </div>
    );
  } 
  else {
    popup_form = (
      <div>
        <form onSubmit={login_handle}>
          <h5>Sign In</h5>
          <input type="text" placeholder="Username" value={username} onChange={(e) => set_user(e.target.value)} />
          <input type="password" placeholder="Password" value={password} onChange={(e) => set_pass(e.target.value)} />
          <button type="submit">Sign In</button>
          {message && <p>{message}</p>}
        </form>
        <p>Don't have an account? <button onClick={() => set_register_toggle(true)}>Register</button></p>
      </div>
    );
  }

  return <div className="dropdown-menu">{popup_form}</div>;
}