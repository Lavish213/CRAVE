import React from 'react';
import { TouchableOpacity } from 'react-native';

export const animateToRegionMock = jest.fn();
export const fitToCoordinatesMock = jest.fn();
export const mapViewProps: { current: any } = { current: null };

const MapView = React.forwardRef((props: any, ref: any) => {
  mapViewProps.current = props;
  React.useImperativeHandle(ref, () => ({
    animateToRegion: animateToRegionMock,
    fitToCoordinates: fitToCoordinatesMock,
  }));
  return React.createElement(React.Fragment, null, props.children);
});

export default MapView;
// Renders a real pressable (rather than null) so a test can simulate a
// marker tap via its testID -- map.tsx passes one per feature/cluster.
// Existing tests that don't care about marker presses are unaffected;
// they never queried for these elements before.
export const Marker = ({ onPress, testID, children }: any) =>
  React.createElement(TouchableOpacity, { onPress, testID }, children);
export type Region = {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
};
