import React from 'react';
import './profile.css';

const Profile = () => {
  const username = localStorage.getItem('username');

  let greeting;
  let message;
  if (username) {
    greeting = <h3>Welcome, {username}!</h3>;
    message = <p>This is your profile page, let us know more about you!</p>;
  } 
  else {
    greeting = <h3>Welcome, new friend!</h3>;
    message = <p>Please log in to view your profile and join our vibes!</p>;
  }

  return (
    <div>
      {greeting}
      {message}

      {username && (//only renders when user logged in
        <form className='profile'>
          <div>
            <label>Email: </label>
            <input/>
          </div>
          <div>
            <label>Gender: </label>
            <input/>
          </div>
          <div>
            <label>Country/Region: </label>
            <input/>
          </div>
          <div>
            <label>Musical preferences: </label>
            <input/>
          </div>
        </form>
      )}

      <a className='construction'>🚧This page is under construction, more features coming soon!🚧</a>
      <a href="/" className="home-link">Return to Home</a>
    </div>
  );
};

export default Profile;
