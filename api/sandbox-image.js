import { ImageResponse } from '@takumi-rs/image-response';
import React from 'react';
import { decodeCode, formatGBP, formatShort } from './decode.js';

export default async function handler(req) {
  try {
    const url = new URL(req.url, 'http://localhost');
    const id = url.searchParams.get('id');

    if (!id) {
      return new Response('Missing ID', { status: 400 });
    }

    const decoded = decodeCode(id);
    if (!decoded) {
      return new Response('Invalid ID', { status: 400 });
    }

    const { spentItems, totalCost } = decoded;

    // Show up to 5 items on the receipt card
    const displayItems = spentItems.slice(0, 5);
    const remainingCount = spentItems.length - 5;

    return new ImageResponse(
      React.createElement(
        'div',
        {
          style: {
            display: 'flex',
            flexDirection: 'column',
            width: '100%',
            height: '100%',
            backgroundColor: '#f7f4ee',
            fontFamily: 'sans-serif',
            color: '#23211c',
            padding: '40px',
            boxSizing: 'border-box',
            border: '12px solid #7a2419',
            justifyContent: 'space-between',
          },
        },
        // Header block
        React.createElement(
          'div',
          {
            style: {
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '2px solid #e4dfd2',
              paddingBottom: '15px',
              width: '100%',
            },
          },
          React.createElement(
            'div',
            { style: { display: 'flex', flexDirection: 'column' } },
            React.createElement(
              'span',
              {
                style: {
                  fontSize: '14px',
                  fontWeight: 'bold',
                  color: '#7a2419',
                  letterSpacing: '2px',
                  textTransform: 'uppercase',
                },
              },
              'The Subsidy Clock'
            ),
            React.createElement(
              'span',
              {
                style: {
                  fontSize: '28px',
                  fontWeight: 'bold',
                  fontFamily: 'Georgia, serif',
                },
              },
              'What Could It Buy?'
            )
          ),
          React.createElement(
            'div',
            {
              style: {
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
              },
            },
            React.createElement(
              'span',
              {
                style: {
                  fontSize: '12px',
                  color: '#5d6470',
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                },
              },
              'Receipt Number'
            ),
            React.createElement(
              'span',
              { style: { fontSize: '16px', fontWeight: 'bold' } },
              `#${id.slice(0, 8)}`
            )
          )
        ),
        // Content body
        React.createElement(
          'div',
          {
            style: {
              display: 'flex',
              flex: 1,
              marginTop: '25px',
              gap: '40px',
              width: '100%',
              minHeight: '0',
            },
          },
          // Left: Receipt details
          React.createElement(
            'div',
            {
              style: {
                display: 'flex',
                flexDirection: 'column',
                flex: 1.3,
                backgroundColor: '#fffdf9',
                border: '1px dashed #d9d2c4',
                borderRadius: '8px',
                padding: '24px',
                justifyContent: 'space-between',
              },
            },
            React.createElement(
              'div',
              { style: { display: 'flex', flexDirection: 'column', gap: '10px' } },
              React.createElement(
                'div',
                {
                  style: {
                    fontSize: '12px',
                    fontWeight: 'bold',
                    color: '#5d6470',
                    borderBottom: '1px solid #e7e1d4',
                    paddingBottom: '6px',
                    textTransform: 'uppercase',
                    letterSpacing: '1px',
                  },
                },
                'Itemized Purchase'
              ),
              displayItems.length === 0
                ? React.createElement(
                    'div',
                    {
                      style: {
                        fontSize: '16px',
                        color: '#8f94a0',
                        fontStyle: 'italic',
                      },
                    },
                    'No items spent yet.'
                  )
                : displayItems.map((item, idx) =>
                    React.createElement(
                      'div',
                      {
                        key: idx,
                        style: {
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          fontSize: '15px',
                          margin: '2px 0',
                        },
                      },
                      React.createElement(
                        'div',
                        {
                          style: {
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                          },
                        },
                        React.createElement('span', {
                          style: {
                            width: '8px',
                            height: '8px',
                            borderRadius: '2px',
                            backgroundColor: item.color,
                            display: 'inline-block',
                          },
                        }),
                        React.createElement(
                          'span',
                          { style: { fontWeight: '500' } },
                          item.name
                        ),
                        React.createElement(
                          'span',
                          { style: { color: '#8f94a0', fontSize: '13px' } },
                          `×${item.count}`
                        )
                      ),
                      React.createElement(
                        'span',
                        { style: { fontWeight: 'bold' } },
                        formatShort(item.totalCost)
                      )
                    )
                  ),
              remainingCount > 0
                ? React.createElement(
                    'div',
                    {
                      style: {
                        fontSize: '14px',
                        color: '#8f94a0',
                        fontStyle: 'italic',
                        marginTop: '4px',
                      },
                    },
                    `... and ${remainingCount} more item${remainingCount > 1 ? 's' : ''}`
                  )
                : null
            ),
            React.createElement(
              'div',
              {
                style: {
                  display: 'flex',
                  justifyContent: 'space-between',
                  borderTop: '1px dashed #d9d2c4',
                  paddingTop: '10px',
                  fontSize: '13px',
                  color: '#5d6470',
                },
              },
              React.createElement('span', null, 'Tax/Subsidy Rate'),
              React.createElement('span', null, '100% Sourced')
            )
          ),
          // Right: Total spent
          React.createElement(
            'div',
            {
              style: {
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
                justifyContent: 'center',
                alignItems: 'flex-start',
                paddingLeft: '20px',
              },
            },
            React.createElement(
              'span',
              {
                style: {
                  fontSize: '14px',
                  fontWeight: 'bold',
                  color: '#5d6470',
                  textTransform: 'uppercase',
                  letterSpacing: '2px',
                },
              },
              'Total Spent'
            ),
            React.createElement(
              'span',
              {
                style: {
                  fontSize: '56px',
                  fontWeight: 'bold',
                  color: '#99311f',
                  fontFamily: 'Georgia, serif',
                  margin: '5px 0',
                },
              },
              formatGBP(totalCost)
            ),
            React.createElement(
              'div',
              {
                style: {
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  borderTop: '1px solid #e4dfd2',
                  width: '100%',
                  paddingTop: '15px',
                  marginTop: '10px',
                },
              },
              React.createElement(
                'span',
                { style: { fontSize: '14px', color: '#23211c' } },
                'Paid directly to UK generators since 2002.'
              ),
              React.createElement(
                'span',
                { style: { fontSize: '12px', color: '#8f94a0', marginTop: '8px' } },
                'Create your own at subsidyclock.co.uk'
              )
            )
          )
        ),
        // Footer block
        React.createElement(
          'div',
          {
            style: {
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderTop: '1px solid #e4dfd2',
              paddingTop: '12px',
              fontSize: '11px',
              color: '#8f94a0',
              width: '100%',
            },
          },
          React.createElement(
            'span',
            null,
            'EVERY FIGURE TRACES TO AN OFFICIAL SOURCE'
          ),
          React.createElement('span', null, 'subsidyclock.co.uk/buy')
        )
      ),
      {
        width: 1200,
        height: 630,
      }
    );
  } catch (error) {
    console.error('Error generating OpenGraph image', error);
    return new Response('Internal Server Error', { status: 500 });
  }
}
