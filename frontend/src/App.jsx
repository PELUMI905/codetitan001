import { useEffect, useState } from 'react';
import './style.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function apiRequest(path, options = {}) {
  const token = localStorage.getItem('ct_token');
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Something went wrong. Please try again.');
  return data;
}

export default function App() {
  const [destinations, setDestinations] = useState([]);
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [authMode, setAuthMode] = useState('');
  const [bookingDestination, setBookingDestination] = useState(null);
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ct_user') || 'null'); } catch { return null; }
  });
  const [bookings, setBookings] = useState([]);
  const [showBookings, setShowBookings] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [adminBookings, setAdminBookings] = useState([]);
  const [loadingDestinations, setLoadingDestinations] = useState(true);

  const loadDestinations = async (search = '') => {
    setLoadingDestinations(true);
    try {
      const result = await apiRequest(`/api/destinations${search ? `?q=${encodeURIComponent(search)}` : ''}`);
      setDestinations(result);
    } catch (error) {
      setNotice(`Could not load destinations: ${error.message}. Check that the backend is running.`);
    } finally {
      setLoadingDestinations(false);
    }
  };

  const loadBookings = async () => {
    try { setBookings(await apiRequest('/api/bookings/me')); }
    catch (error) { setNotice(error.message); }
  };

  useEffect(() => {
    loadDestinations();
    if (localStorage.getItem('ct_token')) loadBookings();
    const onScroll = () => document.querySelector('.header')?.classList.toggle('active', window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
    // Run once on mount; load functions intentionally use the current API URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = async (event) => {
    event.preventDefault();
    await loadDestinations(query.trim());
    document.getElementById('destinations')?.scrollIntoView({ behavior: 'smooth' });
    setMenuOpen(false);
  };

  const handleAuth = async (event) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const payload = authMode === 'register'
      ? { name: values.get('name'), email: values.get('email'), password: values.get('password') }
      : { email: values.get('email'), password: values.get('password') };
    try {
      const result = await apiRequest(`/api/auth/${authMode}`, { method: 'POST', body: JSON.stringify(payload) });
      localStorage.setItem('ct_token', result.access_token);
      localStorage.setItem('ct_user', JSON.stringify(result.user));
      setUser(result.user);
      setAuthMode('');
      setNotice(`Welcome${result.user.name ? `, ${result.user.name}` : ''}! You are signed in.`);
      await loadBookings();
    } catch (error) { setNotice(error.message); }
  };

  const handleBooking = async (event) => {
    event.preventDefault();
    if (!user) {
      setBookingDestination(null);
      setAuthMode('login');
      setNotice('Please sign in or create an account before booking.');
      return;
    }
    const values = new FormData(event.currentTarget);
    try {
      const result = await apiRequest('/api/bookings', {
        method: 'POST',
        body: JSON.stringify({
          destination_id: bookingDestination.id,
          travel_date: values.get('travel_date'),
          travelers: Number(values.get('travelers')),
          notes: values.get('notes') || '',
        }),
      });
      setNotice(`Booking request #${result.id} submitted. It is a request, not a confirmed ticket.`);
      setBookingDestination(null);
      setShowBookings(true);
      await loadBookings();
    } catch (error) { setNotice(error.message); }
  };

  const handleSubscribe = async (event) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try {
      const result = await apiRequest('/api/newsletter', {
        method: 'POST',
        body: JSON.stringify({
          name: values.get('name'), email: values.get('email'),
          country: values.get('country'), phone: values.get('phone') || '',
        }),
      });
      setNotice(result.message);
      event.currentTarget.reset();
    } catch (error) { setNotice(error.message); }
  };

  const cancelBooking = async (id) => {
    try {
      const result = await apiRequest(`/api/bookings/${id}/cancel`, { method: 'PATCH' });
      setNotice(result.message);
      await loadBookings();
    } catch (error) { setNotice(error.message); }
  };

  const loadAdminBookings = async () => {
    try { setAdminBookings(await apiRequest('/api/admin/bookings')); }
    catch (error) { setNotice(error.message); }
  };

  const createDestination = async (event) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try {
      await apiRequest('/api/admin/destinations', { method: 'POST', body: JSON.stringify({
        name: values.get('name'), country: values.get('country'), description: values.get('description'),
        price: Number(values.get('price')), image: values.get('image') || '/images/category-1.jpg',
        featured: values.get('featured') === 'on', active: true,
      }) });
      setNotice('Destination added successfully.');
      event.currentTarget.reset();
      await loadDestinations();
      await loadAdminBookings();
    } catch (error) { setNotice(error.message); }
  };

  const hideDestination = async (id) => {
    try {
      const result = await apiRequest(`/api/admin/destinations/${id}`, { method: 'DELETE' });
      setNotice(result.message);
      await loadDestinations();
    } catch (error) { setNotice(error.message); }
  };

  const logout = () => {
    localStorage.removeItem('ct_token');
    localStorage.removeItem('ct_user');
    setUser(null);
    setBookings([]);
    setShowBookings(false);
    setNotice('You have signed out.');
  };

  return (
    <>
      <header className="header">
        <a className="logo" href="#home"><i className="fas fa-hiking" /> CodeTitan<span className="brand-dot">.</span></a>
        <nav className={`navbar ${menuOpen ? 'active' : ''}`}>
          <a href="#home" onClick={() => setMenuOpen(false)}>Home</a>
          <a href="#about" onClick={() => setMenuOpen(false)}>About</a>
          <a href="#destinations" onClick={() => setMenuOpen(false)}>Destinations</a>
          <a href="#why-us" onClick={() => setMenuOpen(false)}>Why us</a>
          <a href="#subscribe" onClick={() => setMenuOpen(false)}>Subscribe</a>
        </nav>
        <div className="header-actions">
          <button className="icon-button" aria-label="Open menu" onClick={() => setMenuOpen((value) => !value)}><i className="fas fa-bars" /></button>
          {user ? <button className="account-button" onClick={() => { setShowBookings((value) => !value); loadBookings(); }}><i className="fas fa-user" /> My trips</button> : <button className="account-button" onClick={() => setAuthMode('login')}><i className="fas fa-user" /> Sign in</button>}
        </div>
      </header>

      {notice && <div className="site-notice" role="status"><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss message">×</button></div>}

      {user && showBookings && <aside className="ct-bookings-panel">
        <div className="panel-heading"><h2>My booking requests</h2><button onClick={() => setShowBookings(false)} aria-label="Close bookings">×</button></div>
        {bookings.length === 0 ? <p className="empty-bookings">You have no booking requests yet.</p> : bookings.map((booking) => (
          <article className="ct-booking-row" key={booking.id}>
            <div><strong>#{booking.id} · {booking.destination}</strong><p>{booking.country} · {booking.travel_date} · {booking.travelers} traveller(s)</p><span className={`ct-status ct-status-${booking.status}`}>{booking.status}</span></div>
            {booking.status === 'pending' && <button className="small-action" onClick={() => cancelBooking(booking.id)}>Cancel</button>}
          </article>
        ))}
        {user.role === 'admin' && <button className="small-action admin-open-button" onClick={() => { setShowAdmin((value) => !value); loadAdminBookings(); }}> {showAdmin ? 'Close admin tools' : 'Open admin tools'} </button>}
        <button className="small-action logout-button" onClick={logout}>Sign out</button>
      </aside>}

      {user?.role === 'admin' && showAdmin && <aside className="ct-admin-panel"><div className="panel-heading"><h2>CodeTitan admin</h2><button onClick={() => setShowAdmin(false)} aria-label="Close admin panel">×</button></div><h3>Add a destination</h3><form className="admin-destination-form" onSubmit={createDestination}><input name="name" placeholder="Destination name" required minLength="2" /><input name="country" placeholder="Country" required minLength="2" /><textarea name="description" placeholder="Description (at least 10 characters)" required minLength="10" maxLength="1000" rows="3" /><input name="price" type="number" placeholder="Guide price in NGN" required min="0" /><input name="image" placeholder="Image path, e.g. /images/category-1.jpg" /><label className="admin-checkbox"><input name="featured" type="checkbox" /> Feature this destination</label><button className="small-action" type="submit">Add destination</button></form><h3>Manage destinations</h3>{destinations.map((destination) => <div className="admin-destination-row" key={destination.id}><span>{destination.name} · ₦{Number(destination.price).toLocaleString('en-NG')}</span><button className="small-action" onClick={() => hideDestination(destination.id)}>Hide</button></div>)}<h3>Recent booking requests</h3>{adminBookings.length === 0 ? <p className="empty-bookings">No booking requests yet.</p> : adminBookings.map((booking) => <div className="admin-destination-row" key={booking.id}><span>#{booking.id} {booking.customer_name} — {booking.destination} ({booking.travel_date}) · {booking.status}</span></div>)}</aside>}

      <main>
        <section className="ct-hero" id="home">
          <div className="ct-hero-content">
            <span className="eyebrow"><i className="fas fa-globe-africa" /> YOUR NEXT ADVENTURE STARTS HERE</span>
            <h1>Travel more.<br /><span>Worry less.</span></h1>
            <p>Find beautiful places, plan your next getaway, and send a travel booking request with CodeTitan.</p>
            <div className="hero-actions"><a className="btn" href="#destinations">Explore destinations <i className="fas fa-arrow-right" /></a><a className="text-link" href="#about">Discover CodeTitan</a></div>
            <div className="hero-trust"><span><i className="fas fa-check-circle" /> Curated destinations</span><span><i className="fas fa-check-circle" /> Simple booking requests</span></div>
          </div>
          <div className="ct-hero-image"><img src="/images/home-bg-1.jpg" alt="Mountain landscape for a travel adventure" /><div className="floating-card"><span className="floating-icon"><i className="fas fa-map-marked-alt" /></span><div><strong>Find your escape</strong><p>From local gems to world wonders</p></div></div></div>
        </section>

        <section className="ct-search-section" aria-label="Search destinations">
          <form className="ct-search-form" onSubmit={handleSearch}>
            <label><span><i className="fas fa-search" /> Where do you want to go?</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try Paris, Nigeria, beach..." /></label>
            <button className="btn" type="submit">Search trips</button>
          </form>
        </section>

        <section className="ct-about" id="about">
          <div className="about-image"><img src="/images/about-img.jpg" alt="Travellers exploring a scenic destination" /><div className="about-image-tag"><strong>Go beyond</strong><span>the ordinary</span></div></div>
          <div className="about-copy"><span className="eyebrow">ABOUT CODETITAN TRAVEL</span><h2>Make every journey <span>mean something.</span></h2><p>We help you explore travel inspiration in one place. Browse destinations, compare guide prices, and submit a trip request when you are ready to plan.</p><div className="about-points"><p><i className="fas fa-check-circle" /> Destinations loaded from our database</p><p><i className="fas fa-check-circle" /> Personal booking request history</p><p><i className="fas fa-check-circle" /> Friendly, simple planning experience</p></div><a className="btn" href="#destinations">Find a destination</a></div>
        </section>

        <section className="ct-live-destinations" id="destinations">
          <div className="section-title"><span className="eyebrow">PICK YOUR NEXT STOP</span><h2>Explore <span>destinations</span></h2><p>Destination details and sample guide prices are retrieved from the CodeTitan database.</p></div>
          {query && <p className="ct-search-summary">Showing results for “{query}”. <button onClick={() => { setQuery(''); loadDestinations(); }}>Clear search</button></p>}
          {loadingDestinations ? <p className="ct-empty">Loading destinations…</p> : <div className="ct-destination-grid">
            {destinations.map((destination) => <article className="ct-destination-card" key={destination.id}>
              <div className="destination-photo"><img src={destination.image || '/images/category-1.jpg'} alt={destination.name} loading="lazy" /><span className="destination-country">{destination.country}</span></div>
              <div className="ct-destination-content"><h3>{destination.name}</h3><p>{destination.description}</p><div className="ct-card-bottom"><div><small>Guide price from</small><strong>₦{Number(destination.price).toLocaleString('en-NG')}</strong></div><button className="btn" onClick={() => setBookingDestination(destination)}>Book trip</button></div></div>
            </article>)}
            {destinations.length === 0 && <p className="ct-empty">No destinations found. Try a different search.</p>}
          </div>}
          <p className="price-note">Prices shown are sample guide prices only. Booking requests are not confirmed tickets or hotel reservations.</p>
        </section>

        <section className="ct-why-us" id="why-us"><div className="section-title"><span className="eyebrow">TRAVEL WITH CONFIDENCE</span><h2>Made for your <span>next adventure</span></h2></div><div className="why-grid"><article><i className="fas fa-map-marked-alt" /><h3>Inspiring places</h3><p>Explore local and international destination ideas.</p></article><article><i className="fas fa-calendar-check" /><h3>Easy trip requests</h3><p>Choose your travel date and number of travellers.</p></article><article><i className="fas fa-user-shield" /><h3>Your own account</h3><p>Sign in to review your booking requests and cancel pending ones.</p></article></div></section>

        <section className="newsletter" id="subscribe"><div className="content"><span className="eyebrow">LET THE JOURNEY CONTINUE</span><h2 className="heading">Get travel inspiration</h2><p>Subscribe for updates from CodeTitan Travel.</p><form onSubmit={handleSubscribe}><input name="name" type="text" placeholder="Your name" required minLength="2" /><input name="email" type="email" placeholder="Your email address" required /><select name="country" defaultValue="Nigeria" aria-label="Country"><option>Nigeria</option><option>Ghana</option><option>South Africa</option><option>United Kingdom</option><option>United States</option><option>Other</option></select><input name="phone" type="tel" placeholder="Phone number (optional)" /><button className="btn" type="submit">Subscribe <i className="fas fa-paper-plane" /></button></form></div></section>
      </main>

      <footer className="ct-footer"><a className="logo" href="#home"><i className="fas fa-hiking" /> CodeTitan<span className="brand-dot">.</span></a><p>Find your next adventure, one destination at a time.</p><div className="footer-links"><a href="#about">About</a><a href="#destinations">Destinations</a><a href="#subscribe">Subscribe</a><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API docs</a></div><small>© {new Date().getFullYear()} CodeTitan Travel. All rights reserved.</small></footer>

      {authMode && <div className="ct-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setAuthMode(''); }}><section className="ct-modal" role="dialog" aria-modal="true" aria-labelledby="auth-title"><button className="ct-modal-close" onClick={() => setAuthMode('')} aria-label="Close">×</button><span className="eyebrow">WELCOME TO CODETITAN</span><h2 id="auth-title">{authMode === 'register' ? 'Create your account' : 'Welcome back'}</h2><p>Sign in to manage your travel booking requests.</p><form onSubmit={handleAuth}>{authMode === 'register' && <label>Full name<input name="name" required minLength="2" autoComplete="name" /></label>}<label>Email address<input type="email" name="email" required autoComplete="email" /></label><label>Password<input type="password" name="password" required minLength={authMode === 'register' ? 8 : 1} autoComplete={authMode === 'register' ? 'new-password' : 'current-password'} /></label><button className="btn" type="submit">{authMode === 'register' ? 'Create account' : 'Sign in'}</button></form><p className="ct-switch">{authMode === 'register' ? 'Already registered?' : 'New to CodeTitan?'} <button onClick={() => setAuthMode(authMode === 'register' ? 'login' : 'register')}>{authMode === 'register' ? 'Sign in' : 'Create an account'}</button></p></section></div>}

      {bookingDestination && <div className="ct-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setBookingDestination(null); }}><section className="ct-modal" role="dialog" aria-modal="true" aria-labelledby="booking-title"><button className="ct-modal-close" onClick={() => setBookingDestination(null)} aria-label="Close">×</button><span className="eyebrow">PLAN YOUR NEXT TRIP</span><h2 id="booking-title">Request a trip to {bookingDestination.name}</h2><p>{bookingDestination.country} · sample guide price ₦{Number(bookingDestination.price).toLocaleString('en-NG')} per traveller</p><form onSubmit={handleBooking}><label>Travel date<input type="date" name="travel_date" required min={new Date().toISOString().slice(0, 10)} /></label><label>Number of travellers<input type="number" name="travelers" required min="1" max="20" defaultValue="1" /></label><label>Notes (optional)<textarea name="notes" rows="3" maxLength="500" placeholder="Tell us anything we should know" /></label><button className="btn" type="submit">Submit booking request</button></form><small>Submitting creates a request. It does not confirm a ticket, hotel, or payment.</small></section></div>}
    </>
  );
}
