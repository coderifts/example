/** Shared contract fixtures. Mirror of specs.py. */

export const OLD_SPEC = {
  openapi: '3.0.0',
  info: { title: 'Orders API', version: '1.0.0' },
  paths: {
    '/orders/{id}': { get: { summary: 'Get an order', responses: { 200: { description: 'OK' } } } },
  },
};

/** Breaking: the endpoint the agent calls is gone. */
export const UNSAFE_NEW_SPEC = {
  openapi: '3.0.0',
  info: { title: 'Orders API', version: '2.0.0' },
  paths: {},
};

/** Non-breaking: same endpoint, one added optional response field. */
export const SAFE_NEW_SPEC = {
  openapi: '3.0.0',
  info: { title: 'Orders API', version: '1.1.0' },
  paths: {
    '/orders/{id}': {
      get: {
        summary: 'Get an order',
        responses: {
          200: {
            description: 'OK',
            content: {
              'application/json': {
                schema: {
                  type: 'object',
                  properties: { id: { type: 'string' }, status: { type: 'string' } },
                },
              },
            },
          },
        },
      },
    },
  },
};
