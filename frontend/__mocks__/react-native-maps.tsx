import React from 'react';

export const animateToRegionMock = jest.fn();
export const mapViewProps: { current: any } = { current: null };

const MapView = React.forwardRef((props: any, ref: any) => {
  mapViewProps.current = props;
  React.useImperativeHandle(ref, () => ({
    animateToRegion: animateToRegionMock,
  }));
  return React.createElement(React.Fragment, null, props.children);
});

export default MapView;
export const Marker = (_props: any) => null;
export type Region = {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
};
