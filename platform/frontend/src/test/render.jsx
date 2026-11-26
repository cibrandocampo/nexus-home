import { render } from '@testing-library/react';
import { useEffect } from 'react';
import { MemoryRouter, useLocation } from 'react-router';

import { createQueryClient } from '../api/queryClient';
import { Providers } from '../Providers';

function LocationSpy({ onLocation }) {
  const location = useLocation();
  useEffect(() => {
    onLocation(location);
  }, [location, onLocation]);
  return null;
}

// `router.location` is the current location, for tests that check where the app navigated.
export function renderWithProviders(ui, { route = '/' } = {}) {
  const queryClient = createQueryClient();
  const router = { location: null };
  return {
    queryClient,
    router,
    ...render(
      <Providers queryClient={queryClient} env="test">
        <MemoryRouter initialEntries={[route]}>
          {ui}
          <LocationSpy onLocation={(location) => (router.location = location)} />
        </MemoryRouter>
      </Providers>,
    ),
  };
}
